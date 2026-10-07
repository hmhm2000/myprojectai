from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from core.errors import BadRequest, NotFound
from database.db import get_db
from models.user import User
from schemas.user import UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=List[UserResponse])
def get_users(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.put("/{user_id}/toggle-admin", response_model=UserResponse)
def toggle_admin(user_id: int, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise BadRequest("users.cannot_change_own_role", "You cannot change your own admin role")
    user = db.get(User, user_id)
    if not user:
        raise NotFound("users.not_found", "User not found")
    user.is_admin = not user.is_admin
    db.commit()
    db.refresh(user)
    return user
