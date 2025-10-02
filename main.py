from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn



app = FastAPI()

import os
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")


active_connections = {} 
message_history = []
user_counter = 0

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_connections, message_history, user_counter

    await websocket.accept()
    
    user_counter+=1
    username = f"User {user_counter}"

    active_connections[websocket] = {
        "username": username,
        "room": "General"
    }

    print(f"Client connected: {username}. Total connections: {len(active_connections)}")

    user_room = active_connections[websocket]["room"]

    for msg in message_history:
        if msg["room"] == user_room:  # Only send messages from their room
            historical_message = f"[{msg['room']}] {msg['user']}: {msg['message']}"
            await websocket.send_text(historical_message)

    

    try:
        while True: 
            message = await websocket.receive_text()
            if len(message) > 500:  # Basic length validation
                await websocket.send_text("Error: Message too long")
                continue
            print(f"Received message from {username}: '{message}'")
            print(f"Broadcasting to {len(active_connections)} connections")
            
            message_history.append({"user": username, "message": message, "room": "General"})
            formatted_msg = f"[General] {username}: {message}"

            sender_room = active_connections[websocket]["room"]
            
            for client in active_connections:
                client_room = active_connections[client]["room"]
                
                if client_room == sender_room:  # Only send if in same room
                    await client.send_text(formatted_msg)
                
            print(message_history)

    except WebSocketDisconnect:
        del active_connections[websocket]
        print(f"Client Disconnected: {username}. Total connections: {len(active_connections)}")




@app.get("/")
async def root():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")