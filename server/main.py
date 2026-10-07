import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401  (registers all models)
from api.routes import candles, favorites, journal, portfolios, prices, users
from auth import ensure_admin_account, router as auth_router
from config import settings
from core.errors import AppError, app_error_handler
from database.db import engine
from services.price_service import price_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(module)s]: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App started. Database: %s, registration: %s",
                engine.url, "enabled" if settings.allow_registration else "disabled")
    ensure_admin_account()
    price_service.warm_up_in_background()
    yield


app = FastAPI(title="Crypto Tracker API", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)

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
app.include_router(journal.router)
app.include_router(candles.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
