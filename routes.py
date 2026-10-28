import uuid
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt
from database import get_db
from user_service.models import User

router = APIRouter(prefix="/users", tags=["users"])

SECRET_KEY = "food-waste-redistribution-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/register")
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    password_hash = hash_password(user_data.password)

    user = User(
        user_id=user_id,
        name=user_data.name,
        email=user_data.email,
        password_hash=password_hash,
        role=user_data.role.upper(),
        phone=user_data.phone,
        address=user_data.address,
        latitude=user_data.latitude,
        longitude=user_data.longitude,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.user_id, user.role)
    return {
        "message": "User registered successfully",
        "user_id": user.user_id,
        "token": token,
    }


@router.post("/login")
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.user_id, user.role)
    return {
        "token": token,
        "user_id": user.user_id,
        "role": user.role,
        "name": user.name,
        "address": user.address,
        "latitude": user.latitude,
        "longitude": user.longitude,
    }


@router.get("/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "phone": user.phone,
        "address": user.address,
        "latitude": user.latitude,
        "longitude": user.longitude,
        "created_at": str(user.created_at),
    }


@router.put("/{user_id}")
def update_user(user_id: str, user_data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.name is not None:
        user.name = user_data.name
    if user_data.phone is not None:
        user.phone = user_data.phone
    if user_data.address is not None:
        user.address = user_data.address
    if user_data.latitude is not None:
        user.latitude = user_data.latitude
    if user_data.longitude is not None:
        user.longitude = user_data.longitude

    db.commit()
    db.refresh(user)
    return {
        "message": "User updated successfully",
        "user_id": user.user_id,
        "name": user.name,
        "phone": user.phone,
        "address": user.address,
        "latitude": user.latitude,
        "longitude": user.longitude,
    }


@router.get("")
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role.upper())
    users = query.all()
    return [
        {
            "user_id": u.user_id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "phone": u.phone,
            "address": u.address,
            "latitude": u.latitude,
            "longitude": u.longitude,
            "created_at": str(u.created_at),
        }
        for u in users
    ]
