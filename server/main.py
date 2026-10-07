import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401  (rejestruje wszystkie modele)
from api.routes import favorites, portfolios, prices, users
from auth import ensure_admin_account, router as auth_router
from config import settings
from database.db import engine
from services.price_service import price_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(module)s]: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Start aplikacji. Baza: %s, rejestracja: %s",
                engine.url, "włączona" if settings.allow_registration else "wyłączona")
    ensure_admin_account()
    price_service.warm_up_in_background()
    yield


app = FastAPI(title="Crypto Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users.router)
app.include_router(prices.router)
app.include_router(portfolios.router)
app.include_router(favorites.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
