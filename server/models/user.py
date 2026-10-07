from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from database.db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    favorite_lists = relationship("FavoriteList", back_populates="user", cascade="all, delete-orphan")
