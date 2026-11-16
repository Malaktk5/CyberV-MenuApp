"""Tests de la route WebSocket /ws : protocole ping/pong, diffusion, connexion et déconnexion """
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from concurrent.futures import CancelledError
from app.main import app
from app.routers.ws import CHANNEL
from tests.ws_utils import deadline, get_redis, receive_until


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def r():
    client = get_redis()
    yield client
    client.close()


def numsub(r):
    """Nombre d'abonnés actuellement sur le canal."""
    return r.pubsub_numsub(CHANNEL)[0][1]


def test_ping_returns_pong(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        with deadline():
            assert ws.receive_text() == "pong"


def test_several_pings_on_same_connection(client):
    with client.websocket_connect("/ws") as ws:
        for _ in range(3):
            ws.send_text("ping")
            with deadline():
                assert ws.receive_text() == "pong"

@pytest.mark.xfail(
    raises=CancelledError,
    strict=False,
    reason="Le TestClient (anyio) annule la tâche serveur à la fermeture quand le serveur "
           "publie lui-même dans Redis. Non observé sous uvicorn. Cause exacte non élucidée.",
)
def test_other_message_is_published_and_relayed_back(client):
    msg = f"hello-{uuid.uuid4().hex}"
    with client.websocket_connect("/ws") as ws:
        ws.send_text(msg)  # le serveur le publie dans Redis, puis le relaie aux abonnés
        assert receive_until(ws, msg) == msg

@pytest.mark.xfail(
    raises=CancelledError,
    strict=False,
    reason="Le TestClient (anyio) annule la tâche serveur à la fermeture quand le serveur "
           "publie lui-même dans Redis. Non observé sous uvicorn. Cause exacte non élucidée.",
)
def test_message_is_broadcast_to_all_clients(client):
    msg = f"broadcast-{uuid.uuid4().hex}"
    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        ws1.send_text(msg)
        assert receive_until(ws1, msg) == msg
        assert receive_until(ws2, msg) == msg


def test_can_reconnect_after_disconnect(client):
    for _ in range(2):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            with deadline():
                assert ws.receive_text() == "pong"


def test_connection_subscribes_then_cleans_up_on_disconnect(client, r):
    base = numsub(r)
    with client.websocket_connect("/ws") as ws:
        assert numsub(r) == base + 1  # abonné dès que la connexion est établie
        ws.send_text("ping")
        with deadline():
            assert ws.receive_text() == "pong"
    for _ in range(30):  # la fermeture côté Redis peut prendre quelques ms
        if numsub(r) == base:
            break
        time.sleep(0.1)
    assert numsub(r) == base  # pas de connexion Redis qui traîne après la déconnexion


def test_ws_test_page_is_served(client):
    resp = client.get("/ws-test")
    assert resp.status_code == 200 and "Test WebSocket" in resp.text