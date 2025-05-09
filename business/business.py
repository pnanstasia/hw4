from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import datetime
from fastapi import FastAPI, HTTPException
import os
import requests
from pydantic import BaseModel
from celery.result import AsyncResult
from my_celery import celery_app

app = FastAPI()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your api key")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "myorg")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "logs")

client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)
write_api = client.write_api(write_options=SYNCHRONOUS)

class RecommendationRequest(BaseModel):
    your_song: str
    your_role: str

@app.get("/")
def root():

    point = (
        Point("interaction")
        .tag("service", "web")
        .field("message", "Checking the main page")
        .time(datetime.datetime.utcnow())
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)


    return {"message": "Business logic for music library"}


@app.get("/health")
def health():

    point = (
        Point("interaction")
        .tag("service", "web")
        .field("message", "Checking the health")
        .time(datetime.datetime.utcnow())
    )

    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)

    return {"status": "ok"}

@celery_app.task(bind=True, name='get song reccomendations')
def get_recommend(self, your_song: str):
    self.update_state(state='IN_PROGRESS')
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4o",
        "messages": [{"role": "user", "content": f"Recommend songs similar to {your_song}"}],
        "max_tokens": 50
    }
    response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "No recommendations found")
    else:
        self.update_state(state='FAILURE')
        raise Exception(f"Failed to get recommendations. Status code: {response.status_code}. Response: {response.text}")



@app.post("/recommendations")
def recommend_song(request: RecommendationRequest):
    if request.your_role != 'admin':
        if not os.path.exists("/app/error_reports"):
            os.makedirs("/app/error_reports")

        now = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"/app/error_reports/fraud_{now}.txt"

        with open(filename, "w") as f:
            f.write(f"Time: {datetime.datetime.utcnow()}\n")
            f.write("Alert Type: Fraud attempt \n")
            f.write("Description: Permission denied, your role is wrong")

        raise HTTPException(status_code=403, detail="Permission denied")

    recommendations = get_recommend.delay(request.your_song)
    point = (
    Point("interaction")
        .tag("service", "web")
        .tag("task_id", recommendations.id)
        .time(datetime.datetime.utcnow())
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    return {"task_id": recommendations.id, "status": "Recommendation was received" }

@app.get("/result/{task_id}")
async def get_task_result(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    point = (
        Point("interaction")
        .tag("service", "web")
        .field("status", result.state)
        .time(datetime.datetime.utcnow())
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)

    if result.state == 'PENDING':
        return {"status": "Pending"}
    elif result.state == 'STARTED':
        return {"status": "In Progress"}
    elif result.state == 'SUCCESS':
        return {"status": "Success", "result": result.result}
    elif result.state == 'FAILURE':
        return {"status": "Failed", 
            "error": str(result.result)
        }
    else:
        return {"status": result.state}
