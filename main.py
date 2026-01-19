import json
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
import uvicorn
import asyncio

from database import User, Message, init_db, AsyncSessionLocal
from redis_manager import RedisManager


from auth import register, login, validate_token
from fastapi import status, HTTPException
from pydantic import BaseModel


app = FastAPI()

# request models
class RegisterRequest(BaseModel):
    username: str
    password: str
class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/register")
async def register_endpoint(req: RegisterRequest):
    result = await register(req.username, req.password)
    if result["success"]:
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result["error"]
        )
    
@app.post("/login")
async def login_endpoint(req: LoginRequest):
    result = await login(req.username, req.password)
    if result["success"]:
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["error"]
        )


@app.on_event("startup")
async def startup_event():
    await init_db()
    print("Database Initialized!")

    for room in AVAILABLE_ROOMS:
        await redis_manager.subscribe_to_room(room)
    print(f"Subscribed to rooms: {AVAILABLE_ROOMS}")

    asyncio.create_task(redis_listener())
    print("Redis Listener started!")

import os
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")


active_connections = {} 
user_counter = 0
AVAILABLE_ROOMS = ["General", "Random", "Tech", "Gaming"]
redis_manager = RedisManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    global active_connections, user_counter
    await websocket.accept()
    result = await validate_token(token)
    if not result["success"]:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Invalid token"
        }))
        await websocket.close()
        return
    
    username = result["username"]
    
    active_connections[websocket] = {
        "username": username,
        "room": "General"
    }
    
    await websocket.send_text(json.dumps({
        "type": "room_list",
        "rooms": AVAILABLE_ROOMS
    }))
    user_room = active_connections[websocket]["room"]
    
    #msg_history
    await send_history(websocket, user_room)

    

    try:
        while True: 
            message_data = await websocket.receive_text()
            message = json.loads(message_data)
            message_type = message.get("type")

            if message_type == "switch_room":
                room = message.get("room")

                # async with AsyncSessionLocal as session:
                #     result = await session.execute(
                #         select(Room).where(Room == room)
                #     )
                #     isroom = result.scalar_one_or_none()
                #     if isroom:
                if room in AVAILABLE_ROOMS:
                    
                    active_connections[websocket]["room"] = room

                    #confirm switch
                    await websocket.send_text(json.dumps({
                        "type": "room_switched",
                        "room": room
                    }))

                     #msg_history
                    await send_history(websocket, room)
        
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid room"
                    }))
                

            elif message_type == "chat":
                #chat logic 
                sender_room = active_connections[websocket]["room"]

                if len(message) > 500:  # Basic length validation
                    await websocket.send_text("Error: Message too long")
                    continue
                print(f"Received message from {username}: '{message}'")
                print(f"Broadcasting to {len(active_connections)} connections")

                async with AsyncSessionLocal() as session:
                    new_message = Message(
                        username=username,
                        text=message.get("text"),
                        room=sender_room
                    )
                    session.add(new_message)
                    await session.commit()

                await redis_manager.publish_message(sender_room, username, message.get("text"))


    except WebSocketDisconnect:
        if websocket in active_connections:
            del active_connections[websocket]
        print(f"Client Disconnected: {username}. Total connections: {len(active_connections)}")



async def send_history(websocket: WebSocket, room: str):
    """function to send historical_messages"""
     #msg_history
    async with AsyncSessionLocal() as session:
        # Query messages from database
        result = await session.execute(
            select(Message)
            .where(Message.room == room)
            .order_by(Message.timestamp.asc())
            .limit(50)
        )
        messages = result.scalars().all()
        
        for msg in messages:
            await websocket.send_text(json.dumps({
                "type": "chat",
                "username": msg.username,
                "text": msg.text,
                "room": msg.room
            }))



async def redis_listener():
    """Background task that listens to Redis and broadcasts messages"""
    while True:
        msg = await redis_manager.get_messages()
        
        if msg:
             username = msg["username"]
             text = msg["text"]
             room = msg["room"]

             formatted_msg = json.dumps({
                 "type": "chat",
                 "username": username,
                 "text": text,
                 "room": room
             })

             for client in active_connections:
                 client_room = active_connections[client]["room"]
                 if client_room == room:
                     await client.send_text(formatted_msg)

        await asyncio.sleep(0.01)




@app.get("/")
async def root():
    return RedirectResponse(url="/login.html")

@app.get("/login.html")
async def login_page():
    with open("static/login.html") as f:
        return HTMLResponse(content=f.read())

@app.get("/register.html")
async def register_page():
    with open("static/register.html") as f:
        return HTMLResponse(content=f.read())

@app.get("/chat.html")
async def chat_page():
    with open("static/chat.html") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")