from fastapi import FastAPI, Request
import os
from dotenv import load_dotenv

# .env 파일에 숨겨둔 보안 키들을 로드합니다.
load_dotenv()
CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "NCP 백엔드 서버 구동 중"}

# 라인 챗봇이 메시지를 던져줄 대문 (웹훅)
@app.post("/webhook")
async def line_webhook(request: Request):
    body = await request.json()
    
    # 1. 라인이 보낸 데이터에서 '텍스트 메시지' 추출
    # 2. 네이버 클라우드 PostgreSQL DB에서 과거 데이터 조회 (예정)
    # 3. 네이버 CLOVA Studio API로 문맥 유사도 분석 요청 (예정)
    
    print("====== 라인 수신 데이터 ======")
    print(body)
    print("============================")
    
    return {"status": "success"}