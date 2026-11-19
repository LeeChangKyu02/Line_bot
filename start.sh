cd ~/Desktop/Line_bot
code .
source venv/Scripts/activate
./ngrok http 8000 &
sleep 2
uvicorn main:app --reload
