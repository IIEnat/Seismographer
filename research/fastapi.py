# requires fastapi and uvicorn which can be installed via pip
# run the server with: uvicorn main:app --reload
# will then show a WebSocket client in the browser at http://localhost:8000/

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import random

app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>WebSocket Test</title>
    </head>
    <body>
        <h1>WebSocket Client</h1>
        <ul id='messages'></ul>
        <script>
            const ws = new WebSocket("ws://localhost:8000/ws");
            ws.onmessage = event => {
                const messages = document.getElementById('messages');
                const message = document.createElement('li');
                message.textContent = event.data;
                messages.appendChild(message);
            };
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Simulate real-time data, e.g., seismic reading
            data = random.uniform(-1, 1)
            await websocket.send_text(f"Seismic value: {data:.4f}")
            await asyncio.sleep(1)  # send update every second
    except WebSocketDisconnect:
        print("Client disconnected")
