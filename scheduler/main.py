import time
import os
import requests
from fastapi import FastAPI

app = FastAPI()
MAIN_URL = os.getenv("TARGET_URl", "http://web:8000/health")

def call_main():
    while True:
        try:
            res = requests.get(f"{MAIN_URL}")
            print(f"Sending: {res}", flush=True)
        except Exception as e:
            print("Something went wrong:", e)
        time.sleep(10)

@app.on_event("startup")
async def start_scheduling():
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, call_main)

@app.get("/")
def root():
    return {"status": "app is running ok"}
