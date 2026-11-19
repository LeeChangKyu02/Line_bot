"""
더미 이슈 50개를 임베딩과 함께 DB에 삽입하는 스크립트
실행: python insert_issues_with_embedding.py
"""

import asyncio
import json
import os
import httpx
import aiomysql
from dotenv import load_dotenv

load_dotenv()

CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "linebot")

DUMMY_ISSUES = [
    "And/상품) 상품 상세페이지에서 옵션 선택 후 장바구니 담기 버튼 클릭 시 오류 발생 (스토어동일)",
    "iOS/결제) 결제 완료 후 주문 확인 이메일이 발송되지 않는 문제 (마켓재현)",
    "And/이미지) 모바일 앱에서 이미지 로딩이 느리고 일부 이미지가 표시되지 않음 (store동일)",
    "iOS/회원) 회원가입 시 이메일 인증 코드가 도착하지 않음 (스토어재현)",
    "And/장바구니) 장바구니에 담긴 상품 수량 변경 시 합계 금액이 갱신되지 않음 (마켓동일)",
    "iOS/리뷰) 상품 리뷰 작성 후 등록 버튼 클릭 시 페이지가 멈춤 (store재현)",
    "And/결제) 쿠폰 적용 후 결제 금액 계산이 잘못 표시됨 (스토어동일)",
    "iOS/주문) 주문 취소 요청 후 환불 처리가 되지 않는 문제 (마켓재현)",
    "And/검색) 검색 결과에서 필터 적용 시 상품 목록이 사라짐 (store동일)",
    "iOS/상품) 상품 상세페이지 로딩 중 500 에러 간헐적 발생 (스토어재현)",
    "And/회원) 로그인 후 메인 페이지로 리다이렉트되지 않고 오류 화면 표시 (마켓동일)",
    "iOS/회원) 비밀번호 재설정 링크 클릭 시 만료된 링크라는 메시지 출력 (store재현)",
    "And/주문) 주문 내역에서 배송 추적 버튼 클릭 시 아무 반응 없음 (스토어동일)",
    "iOS/상품) 상품 옵션 중 품절 항목이 선택 가능 상태로 표시됨 (마켓재현)",
    "And/결제) 결제 수단 선택 화면에서 카드 정보 입력 폼이 표시되지 않음 (store동일)",
    "iOS/알림) 앱 푸시 알림 수신 설정 변경 후 반영되지 않음 (스토어재현)",
    "And/마이페이지) 마이페이지에서 주소 추가 저장 시 중복 주소가 등록됨 (마켓동일)",
    "iOS/상품) 상품 목록 페이지 스크롤 시 상단 고정 메뉴가 사라짐 (store재현)",
    "And/결제) 포인트 사용 체크 후 결제 진행 시 포인트가 차감되지 않음 (스토어동일)",
    "iOS/주문) 교환 신청 후 상태가 접수 완료로 변경되지 않음 (마켓재현)",
    "And/앱) iOS 앱에서 특정 화면 진입 시 강제 종료 발생 (store동일)",
    "iOS/상품) 상품 즐겨찾기 추가 버튼 클릭 시 로그인 페이지로 이동하지 않고 오류 (스토어재현)",
    "And/결제) PC 화면에서 결제 완료 팝업이 화면 밖으로 벗어남 (마켓동일)",
    "iOS/검색) 상품 검색 시 한글 입력이 중복되어 입력되는 현상 (store재현)",
    "And/회원) 회원탈퇴 시 연결된 소셜 계정이 해제되지 않음 (스토어동일)",
    "iOS/상품) 상품 상세 페이지 내 판매자 정보 섹션이 표시되지 않음 (마켓재현)",
    "And/장바구니) 장바구니 페이지에서 삭제 버튼 클릭 시 페이지 새로고침 반복 (store동일)",
    "iOS/결제) 결제 완료 후 적립 예정 포인트가 0으로 표시됨 (스토어재현)",
    "And/앱) 앱 첫 실행 시 온보딩 화면이 스킵되지 않음 (마켓동일)",
    "iOS/상품) 특정 카테고리 진입 시 상품이 로드되지 않고 빈 화면 표시 (store재현)",
    "And/주문) 주문 상세에서 배송지 변경 버튼 클릭 시 흰 화면이 뜸 (스토어동일)",
    "iOS/리뷰) 앱에서 이미지 첨부 후 리뷰 등록 시 첨부 이미지가 삭제됨 (마켓재현)",
    "And/어드민) 관리자 페이지에서 상품 등록 시 카테고리 목록이 로드되지 않음 (store동일)",
    "iOS/상품) 상품 상세 내 Q&A 답변 작성 후 저장 버튼이 비활성화 상태 (스토어재현)",
    "And/배송) 정기 배송 설정 변경 후 다음 배송일이 갱신되지 않음 (마켓동일)",
    "iOS/어드민) 입점 판매자 정산 내역 엑셀 다운로드 시 파일이 열리지 않음 (store재현)",
    "And/라이브) 쇼핑 라이브 시청 중 채팅 메시지 전송이 되지 않음 (스토어동일)",
    "iOS/상품) 상품 묶음 할인 적용 시 개별 상품 가격이 잘못 표시됨 (마켓재현)",
    "And/앱) 앱 업데이트 후 로그인 상태가 초기화되는 문제 (store동일)",
    "iOS/배송) GS25 편의점 픽업 선택 시 가능한 매장 목록이 표시되지 않음 (스토어재현)",
    "And/선물) 선물하기 기능에서 수신자 연락처 입력 후 다음 단계로 이동 안 됨 (마켓동일)",
    "iOS/라이브) 라이브 방송 종료 후 VOD 전환이 되지 않는 문제 (store재현)",
    "And/상품) 상품 비교 기능에서 비교 목록에 추가가 되지 않음 (스토어동일)",
    "iOS/회원) 멤버십 등급 변경 후 혜택이 즉시 적용되지 않음 (마켓재현)",
    "And/고객센터) 앱 내 고객센터 채팅 연결 시 대기 시간 안내 없이 연결 끊김 (store동일)",
    "iOS/상품) 브랜드 스토어 페이지에서 팔로우 버튼이 동작하지 않음 (스토어재현)",
    "And/결제) 타임딜 상품 구매 시 카운트다운 타이머가 멈춤 (마켓동일)",
    "iOS/상품) 상품 상세 내 사이즈 가이드 팝업이 열리지 않음 (store재현)",
    "And/결제) 첫 구매 쿠폰이 중복 적용되는 문제 (스토어동일)",
    "iOS/배송) 오늘드림 배송 선택 시 가능 지역인데도 불가 안내가 표시됨 (마켓재현)",
]


async def get_embedding(client: httpx.AsyncClient, text: str) -> list[float]:
    url = "https://clovastudio.stream.ntruss.com/testapp/v1/api-tools/embedding/clir-emb-dolphin"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CLOVA_API_KEY}",
    }
    payload = {"text": text}
    response = await client.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["result"]["embedding"]


async def main():
    print("=== 더미 이슈 삽입 시작 ===\n")

    conn = await aiomysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        charset="utf8mb4",
    )
    cursor = await conn.cursor()

    async with httpx.AsyncClient() as client:
        for i, message in enumerate(DUMMY_ISSUES, 1):
            print(f"[{i:02d}/50] 처리 중: {message[:30]}...")
            try:
                embedding = await get_embedding(client, message)
                embedding_json = json.dumps(embedding)

                sql = """
                    INSERT IGNORE INTO issues
                        (message, keyword, embedding, created_at)
                    VALUES
                        (%s, %s, %s, NOW())
                """
                await cursor.execute(sql, (message, "동일이슈", embedding_json))
                await conn.commit()
                print(f"       ✅ 완료 (임베딩 {len(embedding)}차원)")

            except Exception as e:
                print(f"       ❌ 오류: {e}")

    await cursor.close()
    conn.close()
    print("\n=== 완료! ===")


if __name__ == "__main__":
    asyncio.run(main())