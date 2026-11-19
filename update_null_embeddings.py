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

async def get_embedding(client, text):
    url = "https://clovastudio.stream.ntruss.com/testapp/v1/api-tools/embedding/clir-emb-dolphin"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {CLOVA_API_KEY}"}
    response = await client.post(url, json={"text": text}, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["result"]["embedding"]

async def main():
    conn = await aiomysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset="utf8mb4")
    cursor = await conn.cursor()
    await cursor.execute("SELECT id, message FROM issues WHERE embedding IS NULL")
    rows = await cursor.fetchall()
    print(f"NULL 임베딩 {len(rows)}개 발견\n")
    async with httpx.AsyncClient() as client:
        for issue_id, message in rows:
            print(f"ID {issue_id}: {message[:40]}...")
            try:
                embedding = await get_embedding(client, message)
                await cursor.execute("UPDATE issues SET embedding = %s WHERE id = %s", (json.dumps(embedding), issue_id))
                await conn.commit()
                print(f"  ✅ 완료")
            except Exception as e:
                print(f"  ❌ 오류: {e}")
    await cursor.close()
    conn.close()
    print("\n=== 완료! ===")

if __name__ == "__main__":
    asyncio.run(main())