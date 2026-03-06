from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from database.session import AsyncSessionLocal, get_db
from app.schemas import ServerCreate, ServerRead, TaskCreate, TaskRead
from app.service import (
    NoCapacityError,
    create_server,
    expire_due_tasks,
    list_servers,
    list_tasks,
    place_task,
)


scheduler = AsyncIOScheduler(timezone="UTC")


async def run_expire_job():
    async with AsyncSessionLocal() as db:
        await expire_due_tasks(db, batch_size=settings.expire_batch_size)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_expire_job,
        trigger="interval",
        seconds=settings.ttl_poll_seconds,
        id="expire_due_tasks",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Orchestrator",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/db-ping")
async def db_ping(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"result": result.scalar_one()}


@app.post("/servers", response_model=ServerRead, status_code=201)
async def create_server_route(
    payload: ServerCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_server(db, payload)


@app.get("/servers", response_model=list[ServerRead])
async def list_servers_route(db: AsyncSession = Depends(get_db)):
    return await list_servers(db)


@app.post("/tasks", response_model=TaskRead, status_code=201)
async def create_task_route(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await place_task(db, payload)
    except NoCapacityError:
        raise HTTPException(status_code=409, detail="No capacity on any server")


@app.get("/tasks", response_model=list[TaskRead])
async def list_tasks_route(db: AsyncSession = Depends(get_db)):
    return await list_tasks(db)