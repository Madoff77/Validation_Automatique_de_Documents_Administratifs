from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone, timedelta
import uuid

from api.models.schemas import (
    LoginRequest, TokenResponse, RefreshRequest,
    UserCreate, UserResponse, UserRole
)
from api.auth.jwt_handler import create_access_token, create_refresh_token, verify_refresh_token
from api.auth.password import hash_password, verify_password
from api.dependencies import get_current_user, require_admin
from api.config import settings
from storage.mongo_client import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
from utils.logger import get_logger

router = APIRouter(prefix="/auth", tags=["Authentification"])
logger = get_logger(__name__)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    user = await db.users.find_one({"username": body.username})
    if not user or not verify_password(body.password, user["password_hash"]):
        logger.warning("login_failed", username=body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
        )

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    token_data = {"sub": user["user_id"], "role": user["role"], "username": user["username"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Persister le refresh token
    now_utc = datetime.now(timezone.utc)
    await db.refresh_tokens.insert_one({
        "token": refresh_token,
        "user_id": user["user_id"],
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(days=settings.refresh_token_expire_days),
    })

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    logger.info("login_success", username=body.username, role=user["role"])
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    payload = verify_refresh_token(body.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalide")

    # Vérifier que le token n'est pas révoqué
    stored = await db.refresh_tokens.find_one({"token": body.refresh_token})
    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token révoqué")

    user_id = payload.get("sub")
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    token_data = {"sub": user["user_id"], "role": user["role"], "username": user["username"]}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    # Rotation du refresh token
    now_utc = datetime.now(timezone.utc)
    await db.refresh_tokens.delete_one({"token": body.refresh_token})
    await db.refresh_tokens.insert_one({
        "token": new_refresh_token,
        "user_id": user_id,
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(days=settings.refresh_token_expire_days),
    })

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    await db.refresh_tokens.delete_one({"token": body.refresh_token})
    logger.info("logout", user_id=current_user["user_id"])
    return {"message": "Déconnecté avec succès"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        email=current_user["email"],
        role=current_user["role"],
        full_name=current_user.get("full_name"),
        is_active=current_user.get("is_active", True),
        created_at=current_user["created_at"],
    )


@router.post("/register", response_model=UserResponse)
async def register(
    body: UserCreate,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Création d'un nouvel utilisateur (admin uniquement)."""
    existing = await db.users.find_one({"$or": [{"username": body.username}, {"email": body.email}]})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username ou email déjà utilisé")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_doc = {
        "user_id": user_id,
        "username": body.username,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": body.role.value,
        "full_name": body.full_name,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user_doc)
    logger.info("user_created", username=body.username, role=body.role, by=current_user["username"])

    return UserResponse(
        user_id=user_id,
        username=body.username,
        email=body.email,
        role=body.role,
        full_name=body.full_name,
        is_active=True,
        created_at=now,
    )
