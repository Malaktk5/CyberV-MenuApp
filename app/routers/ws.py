import asyncio
import os

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

router = APIRouter()

CHANNEL = "ws:broadcast"


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    redis = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    await websocket.accept()

    async def relay():
        async for item in pubsub.listen():
            if item["type"] == "message":
                await websocket.send_text(item["data"])

    task = asyncio.create_task(relay())
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
            else:
                await redis.publish(CHANNEL, message)
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        await pubsub.aclose()
        await redis.aclose()


TEST_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Test WebSocket</title></head>
<body>
  <h1>Test WebSocket</h1>
  <p>Etat : <strong id="status" style="color:red">deconnecte</strong></p>
  <input id="msg" placeholder="message">
  <button id="send">Envoyer</button>
  <button id="ping">Ping</button>
  <pre id="log"></pre>
  <script>
    // Listener reutilisable : new WsListener(url, { onMessage, onStatus })
    class WsListener {
      constructor(url, { onMessage = () => {}, onStatus = () => {} } = {}) {
        this.url = url; this.onMessage = onMessage; this.onStatus = onStatus;
        this.retryMs = 1000; this.connect();
      }
      connect() {
        this.socket = new WebSocket(this.url);
        this.socket.onopen = () => { this.retryMs = 1000; this.onStatus(true); };
        this.socket.onmessage = (e) => this.onMessage(e.data);
        this.socket.onclose = () => {
          this.onStatus(false);
          setTimeout(() => this.connect(), this.retryMs);
          this.retryMs = Math.min(this.retryMs * 2, 10000);
        };
      }
      send(text) {
        if (this.socket.readyState === WebSocket.OPEN) this.socket.send(text);
      }
    }

    // Adresse du backend : variable d'environnement WS_PUBLIC_URL, sinon meme hote que la page
    const configured = "__WS_URL__";
    const proto = location.protocol === "https:" ? "wss://" : "ws://";
    const url = configured || (proto + location.host + "/ws");
    const status = document.getElementById("status");
    const log = document.getElementById("log");

    const ws = new WsListener(url, {
      onMessage: (m) => log.append("recu : " + m + "\\n"),
      onStatus: (ok) => {
        status.textContent = ok ? "connecte" : "deconnecte";
        status.style.color = ok ? "green" : "red";
      },
    });
    document.getElementById("send").onclick = () => {
      const v = document.getElementById("msg").value;
      if (v) ws.send(v);
    };
    document.getElementById("ping").onclick = () => ws.send("ping");
  </script>
</body>
</html>
"""


@router.get("/ws-test", response_class=HTMLResponse)
def ws_test_page():
    return TEST_PAGE.replace("__WS_URL__", os.getenv("WS_PUBLIC_URL", ""))
