import logging
import sys
import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, chat, events, auth, users, calendar, rooms, places, intents, meetings, recommendations
from app.api.ws import social as social_ws, agent as agent_ws
from app.core.config import settings
from app.db.session import init_db
from app.services.reminder import run_reminder_job, run_vote_reminder_job

# 구조적 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("maedeup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup_settings()
    logger.info("Starting Maedeup API server")
    await init_db()
    logger.info("Database initialized")
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_reminder_job, trigger="cron", minute=0)
    scheduler.add_job(run_vote_reminder_job, trigger="interval", hours=2)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Scheduler started (reminder job every hour, vote reminder every 2 hours)")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Server shutdown complete")


app = FastAPI(
    title="Maedeup API",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = [settings.FRONTEND_URL]
if settings.APP_ENV.lower() in {"development", "dev"}:
    _cors_origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """요청/응답 로깅 미들웨어."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > 1000:  # 1초 이상 걸린 요청만 경고
        logger.warning(
            "SLOW %s %s → %d (%.0fms)",
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
    return response

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(rooms.router, prefix="/api/v1")
app.include_router(places.router, prefix="/api/v1")
app.include_router(intents.router, prefix="/api/v1")
app.include_router(meetings.router, prefix="/api/v1/meetings")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(social_ws.router)
app.include_router(agent_ws.router)
