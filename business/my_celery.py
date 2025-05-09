from celery import Celery

REDIS_URL = "redis://redis:6379/0"
REDIS_URL_B = "redis://redis:6379/1"
celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL_B,
    include=["business"]
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
