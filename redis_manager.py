import redis.asyncio as redis
import json
import asyncio
import time

class RedisManager:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6380, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
    
    async def publish_message(self, room: str, username: str, text: str):
        """Publish a chat message to Redis"""
        channel = f"chat:{room}"
        message_data = {
            "username": username,
            "text": text,
            "room": room
        }
        await self.redis_client.publish(channel, json.dumps(message_data))
        


    async def subscribe_to_room(self, room: str):
        """Subscribe to messages from a specific room"""
        channel = f"chat:{room}"
        await self.pubsub.subscribe(channel)

    
    async def get_messages(self):
        """Get messages from subscribed channels""" 
        # time.sleep(0.1)
        message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)

        if message and message['type'] == 'message':
            return json.loads(message['data'])
        return None