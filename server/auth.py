import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database.db import SessionLocal, get_db
from models.user import User
from schemas.user import AuthConfig, Token, UserCreate, UserResponse

ALGORITHM = "HS256"

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": username, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise credentials_exception
    if not username:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Insufficient admin privileges")
    return current_user


def ensure_admin_account() -> None:
    """Konto główne z .env: tworzy je, jeśli nie istnieje, albo nadaje mu uprawnienia admina."""
    username = settings.admin_username
    if not username:
        return
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            if not user.is_admin:
                user.is_admin = True
                db.commit()
                logger.info("Użytkownik %s otrzymał uprawnienia admina (ADMIN_USERNAME)", username)
            return
        if not settings.admin_password:
            logger.warning("Brak konta %s i pustego ADMIN_PASSWORD w .env - konto główne nie zostało utworzone", username)
            return
        db.add(User(
            username=username,
            email=settings.admin_email,
            hashed_password=get_password_hash(settings.admin_password),
            is_admin=True,
        ))
        db.commit()
        logger.info("Utworzono konto główne: %s", username)


@router.get("/config", response_model=AuthConfig)
def get_auth_config():
    return AuthConfig(registration_enabled=settings.allow_registration)


@router.post("/register", response_model=Token)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Rejestracja jest wyłączona")
    existing_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Użytkownik lub e-mail już istnieje")
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        is_admin=False,
    )
    db.add(db_user)
    db.commit()
    logger.info("Zarejestrowano użytkownika %s (ID: %s)", db_user.username, db_user.id)
    return Token(access_token=create_access_token(db_user.username), token_type="bearer")


@router.post("/login", response_model=Token)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Nieudane logowanie: %s", form_data.username)
        raise HTTPException(status_code=401, detail="Nieprawidłowe dane logowania")
    return Token(access_token=create_access_token(user.username), token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_current_user_data(current_user: User = Depends(get_current_user)):
    return current_user
