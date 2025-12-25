import os
import json
import redis
import ssl

REDIS_URL = os.getenv("REDIS_URL")

redis_client = redis.from_url(REDIS_URL, decode_responses=True, ssl_cert_reqs=ssl.CERT_NONE, )

QUEUE_NAME = "ci_jobs"

def enqueue_ci_job(payload: dict):
    redis_client.rpush(QUEUE_NAME, json.dumps(payload))
