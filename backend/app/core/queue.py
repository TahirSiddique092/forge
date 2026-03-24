import os
import json
import redis
import ssl

REDIS_URL = os.getenv("REDIS_URL")

redis_client = redis.from_url(REDIS_URL, decode_responses=True, ssl_cert_reqs=ssl.CERT_NONE, )

QUEUE_PREFIX = "ci_jobs"

def enqueue_ci_job(payload: dict):
    queue_name = f"{QUEUE_PREFIX}:{payload['project_id']}"
    redis_client.rpush(queue_name, json.dumps(payload))
