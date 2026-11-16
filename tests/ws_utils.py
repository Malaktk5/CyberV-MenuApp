"""Outils communs aux tests WebSocket / Redis."""
import os
import signal
from contextlib import contextmanager

import pytest
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # même défaut que app/routers/ws.py


@contextmanager
def deadline(seconds=5):
    
    def on_alarm(signum, frame):
        raise TimeoutError(f"Aucun message reçu en {seconds} s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def receive_until(ws, expected, seconds=5):
    
    with deadline(seconds):
        while True:
            msg = ws.receive_text()
            if msg == expected:
                return msg


def get_redis():
    """Client Redis synchrone ; échoue clairement si Redis n'est pas joignable."""
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        r.ping()
    except redis.RedisError as e:
        pytest.fail(f"Redis non joignable sur {REDIS_URL} : {e}")
    return r