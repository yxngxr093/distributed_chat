import secrets
import bcrypt
from database import User, AsyncSessionLocal
from sqlalchemy import select

def hash_password(input_password: str) -> str:
    password_hash = bcrypt.hashpw(input_password.encode('utf-8'), bcrypt.gensalt())
    return password_hash.decode()


def verify_password(input_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(input_password.encode('utf-8'), hashed.encode('utf-8'))

async def register(input_username: str, input_password: str) -> dict:
    async with AsyncSessionLocal() as session:
        # check if username exists
        result = await session.execute(
            select(User).where(User.username == input_username)
        ) 
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return {"success": False, "error": "Username already taken"}
        
        #else create new user
        input_password_hash = hash_password(input_password)
        token = secrets.token_urlsafe(32)

        new_user = User(
            username=input_username,
            password_hash=input_password_hash,
            token=token
        )
        session.add(new_user)
        await session.commit()

        return {"success": True, "token": token, "username": input_username}
    

async def login(input_username: str, input_password: str) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == input_username)
        )
        found_user = result.scalar_one_or_none()

        if not found_user:
            return {"success": False, "error": "Invalid credentials"}
        if not verify_password(input_password, found_user.password_hash):
            return {"success": False, "error": "Invalid credentials"}
        
        return {"success": True, "token": found_user.token, "username": found_user.username}
        

async def validate_token(token:str) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.token == token)
        )
        found_user = result.scalar_one_or_none()

        if not found_user:
            return {"success": False, "error": "Invalid token"}
        
        return {"success": True, "username": found_user.username}