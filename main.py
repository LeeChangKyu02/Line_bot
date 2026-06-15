from fastapi import FastAPI, Request
import os
import httpx
import aiomysql
from dotenv import load_dotenv

# .env 파일에 숨겨둔 보안 키들을 로드합니다.
load_dotenv()
CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
    "charset": "utf8mb4",
}

app = FastAPI()

# ─────────────────────────────────────────
# 키워드 설정 (여기에 원하는 키워드 추가)
# ─────────────────────────────────────────
TRIGGER_KEYWORDS = ["(스토어동일)", "(스토어 동일)", "스토어동일", "스토어 동일"]  # ← 원하는 키워드로 수정


def extract_matched_keywords(message: str) -> list[str]:
    """메시지에서 매칭된 키워드 목록 반환"""
    return [kw for kw in TRIGGER_KEYWORDS if kw in message]


# ─────────────────────────────────────────
# DB 함수들
# ─────────────────────────────────────────
async def get_recent_issues(limit: int = 50):
    """최근 이슈 목록 조회 (같은 키워드 포함된 것만)"""
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "SELECT id, message, keyword FROM issues ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        rows = await cur.fetchall()
    conn.close()
    return rows


async def save_issue(user_id: str, message_id: str, message: str, keyword: str) -> int:
    """새 이슈 저장 (keyword 컬럼 포함)"""
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT IGNORE INTO issues (user_id, message_id, message, keyword, created_at) VALUES (%s, %s, %s, %s, NOW())",
            (user_id, message_id, message, keyword)
        )
        await conn.commit()
        new_id = cur.lastrowid
    conn.close()
    return new_id


async def get_issues_by_keyword(keyword: str, limit: int = 50):
    """같은 키워드의 기존 이슈만 조회 (비교 범위 축소)"""
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "SELECT id, message FROM issues WHERE keyword = %s ORDER BY created_at DESC LIMIT %s",
            (keyword, limit)
        )
        rows = await cur.fetchall()
    conn.close()
    return rows


async def get_issue_by_id(issue_id: int):
    """ID로 이슈 조회"""
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
        row = await cur.fetchone()
    conn.close()
    return row


# ─────────────────────────────────────────
# HyperCLOVA X 유사도 판단
# ─────────────────────────────────────────
async def check_similarity_with_ai(new_message: str, existing_issues: list) -> dict:
    """HyperCLOVA X로 유사 이슈 판단"""
    if not existing_issues:
        return {"isDuplicate": False}

    issue_list = "\n".join(
        [f"[{i+1}] (ID: {issue['id']}) \"{issue['message']}\"" for i, issue in enumerate(existing_issues)]
    )

    prompt = f"""당신은 고객 문의 중복 여부를 판단하는 AI입니다.
아래 규칙을 따르세요:
- 새 문의와 기존 문의의 의미가 유사하면 중복으로 판단합니다.
- 표현이 달라도 핵심 질문이 같으면 중복입니다.
- 반드시 JSON 형식으로만 응답하세요.

새 문의: "{new_message}"

기존 문의 목록:
{issue_list}

응답 형식:
{{"isDuplicate": true/false, "matchedId": 일치하는ID또는null, "similarity": 0.0~1.0, "reason": "판단 이유"}}"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://clovastudio.stream.ntruss.com/testapp/v1/chat-completions/HCX-003",
            headers={
                "Authorization": f"Bearer {CLOVA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [{"role": "user", "content": prompt}],
                "maxTokens": 300,
                "temperature": 0.1,
            },
            timeout=10.0,
        )

    data = response.json()
    text = data.get("result", {}).get("message", {}).get("content", "{}")

    try:
        import json, re
        clean = re.sub(r"```json|```", "", text).strip()
        return json.loads(clean)
    except Exception:
        return {"isDuplicate": False}


# ─────────────────────────────────────────
# LINE 메시지 전송
# ─────────────────────────────────────────
async def reply_message(reply_token: str, messages: list):
    """LINE으로 메시지 응답"""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"replyToken": reply_token, "messages": messages},
        )


# ─────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────
@app.get("/")
def read_root():
    return {"status": "NCP 백엔드 서버 구동 중"}


@app.post("/webhook")
async def line_webhook(request: Request):
    body = await request.json()

    for event in body.get("events", []):
        if event.get("type") != "message":
            continue
        if event.get("message", {}).get("type") != "text":
            continue

        message_id = event["message"]["id"]
        user_message = event["message"]["text"].strip()
        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]

        if not user_message:
            continue

        # ✅ 1단계: 키워드 포함 여부 체크
        matched_keywords = extract_matched_keywords(user_message)

        if not matched_keywords:
            # 키워드 없으면 → 아무 반응 없이 무시 (또는 아래 주석 해제해서 안내 메시지 발송)
            # await reply_message(reply_token, [{"type": "text", "text": "키워드가 포함된 이슈만 접수됩니다."}])
            continue

        # 키워드가 여러 개면 첫 번째 키워드 기준으로 분류
        primary_keyword = matched_keywords[0]

        # ✅ 2단계: 같은 키워드의 기존 이슈만 가져와서 비교 (토큰 절약)
        existing_issues = await get_issues_by_keyword(primary_keyword, limit=50)

        # ✅ 3단계: HyperCLOVA X로 중복 판단
        ai_result = await check_similarity_with_ai(user_message, existing_issues)

        if ai_result.get("isDuplicate") and ai_result.get("matchedId"):
            # 중복 이슈 감지 → 텍스트로 간단하게 응답
            matched = await get_issue_by_id(ai_result["matchedId"])
            matched_text = matched["message"] if matched else "내용을 불러올 수 없습니다."
            similarity = int((ai_result.get("similarity") or 0) * 100)

            await reply_message(reply_token, [
                {
                    "type": "text",
                    "text": f"⚠️ 비슷한 이슈가 이미 있어요!\n\n유사 이슈: {matched_text}\n유사도: {similarity}%"
                }
            ])

        else:
            # 새 이슈 → DB에만 저장, 응답 없음
            await save_issue(user_id, message_id, user_message, primary_keyword)

    return {"status": "success"}