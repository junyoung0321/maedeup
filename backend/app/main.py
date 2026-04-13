import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, chat, events, auth, users, calendar, rooms, places, intents, meetings
from app.api.ws import social as social_ws, agent as agent_ws
from app.db.session import init_db
from app.services.reminder import send_today_meeting_reminders


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        lambda: asyncio.run(send_today_meeting_reminders()),
        trigger="cron",
        minute=0,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Maedeup API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(social_ws.router)
app.include_router(agent_ws.router)
