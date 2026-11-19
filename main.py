from fastapi import FastAPI, Request
import os
import json
import math
import httpx
import aiomysql
from dotenv import load_dotenv

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

TRIGGER_KEYWORDS = ["(스토어동일)", "스토어동일", "(스토어재현)", "스토어재현", "(마켓동일)", "마켓동일", "(마켓재현)", "마켓재현", "(store재현)", "store재현", "(store동일)", "store동일"]
CANONICAL_KEYWORD = "동일이슈"

def extract_matched_keywords(message: str) -> list[str]:
    normalized = message.replace(" ", "")
    return [kw for kw in TRIGGER_KEYWORDS if kw in normalized]

EMBEDDING_THRESHOLD = 0.85
LLM_THRESHOLD = 0.90

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def get_embedding(text: str) -> list[float] | None:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://clovastudio.stream.ntruss.com/testapp/v1/api-tools/embedding/clir-emb-dolphin",
                headers={
                    "Authorization": f"Bearer {CLOVA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
                timeout=30.0,
            )
            data = response.json()
            return data.get("result", {}).get("embedding")
        except Exception as e:
            print(f"[임베딩 오류] {e}")
            return None


async def check_similarity_with_llm(new_message: str, candidates: list) -> dict:
    """유사도 높은 후보만 LLM으로 정밀 판단 - 여러 건 반환"""
    if not candidates:
        return {"isDuplicate": False}

    issue_list = "\n".join(
        [f"(ID: {c['id']}) \"{c['message']}\"" for c in candidates]
    )

    prompt = f"""당신은 고객 문의 중복 여부를 판단하는 AI입니다.
아래 규칙을 따르세요:
- 새 문의와 기존 문의의 의미가 유사하면 중복으로 판단합니다.
- 문장 구조, 어순, 사용 단어가 완전히 달라도 다루는 화면·기능·현상이 같으면 중복입니다.
- 제품명, 색상, 브랜드처럼 부수적인 명사가 달라도 같은 유형의 문의면 중복입니다.
- 현상의 방향이 반대이면 중복이 아닙니다. (예: 마커가 없음 ≠ 마커가 남아있음)
- 단순히 같은 키워드(지도, 마커, 검색 등)가 포함된다고 중복이 아닙니다.
- 확신이 없으면 반드시 중복이 아닌 것으로 판단하세요.

예시:
- "커피를 옷에 쏟았다" = "우유를 옷에 쏟았다" → 중복 (단어 치환)
- "[iOS/설정] 중국어 > 설정 > 번역이 다르게 나와 문의드립니다." = "[iOS/설정] 다국어가 다르게 노출되어 문의드립니다." → 중복 (동일 화면·동일 현상)

반드시 JSON 형식으로만 응답하세요.

새 문의: "{new_message}"

기존 문의 목록:
{issue_list}

응답 형식:
{{"isDuplicate": true/false, "matchedIds": [중복ID목록], "similarity": 0.0~1.0, "reason": "판단 이유"}}"""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://clovastudio.stream.ntruss.com/testapp/v1/chat-completions/HCX-003",
                headers={
                    "Authorization": f"Bearer {CLOVA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "maxTokens": 300,
                    "temperature": 0.3,
                },
                timeout=30.0,
            )
            data = response.json()
            text = data.get("result", {}).get("message", {}).get("content", "{}")
            import re
            clean = re.sub(r"```json|```", "", text).strip()
            return json.loads(clean)
        except Exception as e:
            print(f"[LLM 오류] {e}")
            return {"isDuplicate": False}


async def save_issue(user_id: str, message_id: str, message: str, keyword: str, embedding: list[float] | None) -> int:
    embedding_json = json.dumps(embedding) if embedding else None
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT IGNORE INTO issues (user_id, message_id, message, keyword, embedding, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
            (user_id, message_id, message, keyword, embedding_json)
        )
        await conn.commit()
        new_id = cur.lastrowid
    conn.close()
    return new_id


async def get_issues_with_embedding(keyword: str, limit: int = 5000) -> list:
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            "SELECT id, message, embedding, created_at FROM issues WHERE keyword = %s ORDER BY created_at DESC LIMIT %s",
            (keyword, limit)
        )
        rows = await cur.fetchall()
    conn.close()
    return rows


async def get_issue_by_id(issue_id: int):
    conn = await aiomysql.connect(**DB_CONFIG)
    async with conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
        row = await cur.fetchone()
    conn.close()
    return row


async def reply_message(reply_token: str, messages: list):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"replyToken": reply_token, "messages": messages},
        )


async def push_message(user_id: str, messages: list):
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"to": user_id, "messages": messages},
        )


async def find_duplicate(new_message: str, new_embedding: list[float], keyword: str) -> dict:
    """
    1차: 코사인 유사도로 후보 추림
    2차: 후보 있으면 LLM으로 정밀 판단 (여러 건 반환)
    """
    existing = await get_issues_with_embedding(keyword, limit=200)

    candidates = []
    for issue in existing:
        if not issue["embedding"]:
            continue
        try:
            vec = json.loads(issue["embedding"])
            sim = cosine_similarity(new_embedding, vec)
            if sim >= EMBEDDING_THRESHOLD:
                candidates.append({
                    "id": issue["id"],
                    "message": issue["message"],
                    "similarity": sim,
                    "created_at": issue["created_at"]
                })
        except Exception:
            continue

    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    print(f"[1차 임베딩 필터] 후보 {len(candidates)}건 / 전체 {len(existing)}건")

    if not candidates:
        return {"isDuplicate": False}

    top_candidates = candidates[:10]
    llm_result = await check_similarity_with_llm(new_message, top_candidates)
    print(f"[2차 LLM 판단] {llm_result}")

    # matchedIds로 여러 건 처리
    if llm_result.get("matchedIds"):
        matched_ids = set(llm_result["matchedIds"])
        matched_issues = [c for c in top_candidates if c["id"] in matched_ids]
        if matched_issues:
            llm_result["matchedIssues"] = matched_issues
            llm_result["isDuplicate"] = True
    # 하위 호환: matchedId 단일값도 처리
    elif llm_result.get("matchedId"):
        for c in top_candidates:
            if c["id"] == llm_result["matchedId"]:
                llm_result["matchedIssues"] = [c]
                llm_result["isDuplicate"] = True
                break

    return llm_result


@app.get("/")
def read_root():
    return {"status": "LINE 봇 서버 구동 중 (임베딩 + 하이브리드)"}


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
        source_type = event["source"].get("type", "user")

        if not user_message:
            continue

        # ─── 단체방 처리 ───
        if source_type in ("room", "group"):
            matched_keywords = extract_matched_keywords(user_message)
            if not matched_keywords:
                continue

            primary_keyword = CANONICAL_KEYWORD
            embedding = await get_embedding(user_message)
            if embedding:
                result = await find_duplicate(user_message, embedding, primary_keyword)
                if result.get("isDuplicate"):
                    print(f"[단체방 중복 스킵] keyword={primary_keyword} / user={user_id}")
                else:
                    await save_issue(user_id, message_id, user_message, primary_keyword, embedding)
                    print(f"[단체방 저장] keyword={primary_keyword} / user={user_id}")
            else:
                await save_issue(user_id, message_id, user_message, primary_keyword, None)
                print(f"[단체방 저장-임베딩없음] keyword={primary_keyword} / user={user_id}")

        # ─── 개인 DM 처리 ───
        elif source_type == "user":
            matched_keywords = extract_matched_keywords(user_message)
            if not matched_keywords:
                continue

            primary_keyword = CANONICAL_KEYWORD
            new_embedding = await get_embedding(user_message)
            if not new_embedding:
                await reply_message(reply_token, [{"type": "text", "text": "임베딩 생성 실패. 잠시 후 다시 시도해주세요."}])
                continue

            result = await find_duplicate(user_message, new_embedding, primary_keyword)

            if result.get("isDuplicate") and result.get("matchedIssues"):
                matched_issues = result["matchedIssues"]
                count = len(matched_issues)

                issue_lines = []
                for i, issue in enumerate(matched_issues, 1):
                    time_str = issue["created_at"].strftime("%Y-%m-%d %H:%M") if issue["created_at"] else "시간 정보 없음"
                    similarity = int(issue["similarity"] * 100)
                    issue_lines.append(
                        f"{i}. {issue['message']}\n   등록일시: {time_str} / 유사도: {similarity}%"
                    )

                issues_text = "\n\n".join(issue_lines)
                reply_text = f"⚠️ 유사한 이슈가 {count}건 있어요!\n\n{issues_text}"

                await reply_message(reply_token, [{"type": "text", "text": reply_text}])

            else:
                await reply_message(reply_token, [
                    {"type": "text", "text": "✅ 이슈방_인피닉에 공유 후 새 이슈로 등록하세요!"}
                ])

    return {"status": "success"}