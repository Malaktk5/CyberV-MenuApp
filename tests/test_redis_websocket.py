"""Test de la chaîne Redis Pub/Sub -> WebSocket : un message publié dans Redis arrive au client """
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.ws import CHANNEL
from tests.ws_utils import deadline, get_redis, receive_until


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def r():
    c = get_redis()
    yield c
    c.close()


def wait_ready(ws):
    """Un ping/pong garantit que la boucle de réception du serveur tourne avant de publier."""
    ws.send_text("ping")
    with deadline():
        assert ws.receive_text() == "pong"


def test_message_published_in_redis_reaches_websocket(client, r):
    msg = f"redis-{uuid.uuid4().hex}"
    with client.websocket_connect("/ws") as ws:
        wait_ready(ws)
        receivers = r.publish(CHANNEL, msg)
        assert receivers >= 1  # au moins le serveur WebSocket est abonné au canal
        assert receive_until(ws, msg) == msg


def test_json_payload_is_forwarded_unchanged(client, r):
    payload = json.dumps({"type": "nouvelle_commande", "id": 42, "note": "Crème brûlée"}, ensure_ascii=False)
    with client.websocket_connect("/ws") as ws:
        wait_ready(ws)
        r.publish(CHANNEL, payload)
        received = receive_until(ws, payload)
        assert json.loads(received) == {"type": "nouvelle_commande", "id": 42, "note": "Crème brûlée"}


def test_messages_arrive_in_publication_order(client, r):
    tag = uuid.uuid4().hex
    msgs = [f"{tag}-{i}" for i in range(3)]
    with client.websocket_connect("/ws") as ws:
        wait_ready(ws)
        for m in msgs:
            r.publish(CHANNEL, m)
        with deadline():
            received = [ws.receive_text() for _ in msgs]
        assert received == msgs


def test_message_reaches_every_connected_client(client, r):
    msg = f"multi-{uuid.uuid4().hex}"
    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        wait_ready(ws1)
        wait_ready(ws2)
        assert r.publish(CHANNEL, msg) >= 2
        assert receive_until(ws1, msg) == msg
        assert receive_until(ws2, msg) == msg