from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Server, Task, TaskStatus, PolicyType, ServerStatus
from app.schemas import ServerCreate, TaskCreate


class NoCapacityError(Exception):
    pass


async def create_server(db: AsyncSession, payload: ServerCreate) -> Server:
    server = Server(
        cpu_total=payload.cpu_total,
        ram_total=payload.ram_total,
        gpu_total=payload.gpu_total,
        cpu_free=payload.cpu_total,
        ram_free=payload.ram_total,
        gpu_free=payload.gpu_total,
        status=ServerStatus.RUNNING,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def list_servers(db: AsyncSession) -> list[Server]:
    result = await db.execute(select(Server).order_by(Server.created_at.asc(), Server.uid.asc()))
    return list(result.scalars().all())


async def list_tasks(db: AsyncSession) -> list[Task]:
    result = await db.execute(select(Task).order_by(Task.created_at.desc(), Task.uid.asc()))
    return list(result.scalars().all())


def build_expires_at(ttl_seconds: int | None) -> datetime | None:
    if ttl_seconds is None:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)


def build_server_candidate_stmt(payload: TaskCreate):
    stmt = select(Server).where(
        Server.cpu_free >= payload.cpu_req,
        Server.ram_free >= payload.ram_req,
        Server.gpu_free >= payload.gpu_req,
    )

    if payload.policy == PolicyType.FIRST_FIT:
        stmt = stmt.order_by(Server.created_at.asc(), Server.uid.asc())
    else:
        residual_score = (
            (Server.cpu_free - payload.cpu_req)
            + (Server.ram_free - payload.ram_req)
            + (Server.gpu_free - payload.gpu_req)
        )
        stmt = stmt.order_by(
            residual_score.asc(),
            Server.created_at.asc(),
            Server.uid.asc(),
        )

    return stmt.limit(1).with_for_update(skip_locked=True)


async def place_task(db: AsyncSession, payload: TaskCreate) -> Task:
    expires_at = build_expires_at(payload.ttl_seconds)

    async with db.begin():
        result = await db.execute(build_server_candidate_stmt(payload).where(Server.status == ServerStatus.RUNNING))
        server = result.scalar_one_or_none()

        if server is None:
            task = Task(
                cpu_req=payload.cpu_req,
                ram_req=payload.ram_req,
                gpu_req=payload.gpu_req,
                status=TaskStatus.WAITING,
                expires_at=expires_at,
                server_uid=None,
            )
            db.add(task)
            await db.flush()
            await db.refresh(task)
            return task

        server.cpu_free -= payload.cpu_req
        server.ram_free -= payload.ram_req
        server.gpu_free -= payload.gpu_req

        task = Task(
            cpu_req=payload.cpu_req,
            ram_req=payload.ram_req,
            gpu_req=payload.gpu_req,
            status=TaskStatus.RUNNING,
            expires_at=expires_at,
            server_uid=server.uid,
        )

        db.add(task)
        await db.flush()
        await db.refresh(task)
        return task


async def expire_due_tasks(db: AsyncSession, batch_size: int = 100) -> int:
    now = datetime.now(timezone.utc)

    async with db.begin():
        stmt = (
            select(Task)
            .where(
                Task.status == TaskStatus.RUNNING,
                Task.expires_at.is_not(None),
                Task.expires_at <= now,
            )
            .order_by(Task.expires_at.asc(), Task.uid.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )

        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        for task in tasks:
            task.status = TaskStatus.EXPIRED

            if task.server_uid is not None:
                server_result = await db.execute(select(Server).where(Server.uid == task.server_uid).with_for_update())
                server = server_result.scalar_one_or_none()
                if server is not None:
                    server.cpu_free += task.cpu_req
                    server.ram_free += task.ram_req
                    server.gpu_free += task.gpu_req
                    task.server_uid = None

        return len(tasks)


async def stop_task(db: AsyncSession, task_uid: str) -> Task | None:
    async with db.begin():
        task = await db.get(Task, task_uid)
        if task is None:
            return None
        if task.status == TaskStatus.RUNNING:
            if task.server_uid is not None:
                server = await db.get(Server, task.server_uid)
                if server is not None:
                    server.cpu_free += task.cpu_req
                    server.ram_free += task.ram_req
                    server.gpu_free += task.gpu_req
            task.server_uid = None
        task.status = TaskStatus.STOPPED
        return task


async def stop_server(db: AsyncSession, server_uid: str) -> Server | None:
    async with db.begin():
        server = await db.get(Server, server_uid)
        if server is None:
            return None
        server.status = ServerStatus.STOPPED
        result = await db.execute(
            select(Task).where(Task.server_uid == server_uid, Task.status == TaskStatus.RUNNING).with_for_update()
        )
        tasks = result.scalars().all()
        for task in tasks:
            server.cpu_free += task.cpu_req
            server.ram_free += task.ram_req
            server.gpu_free += task.gpu_req
            task.server_uid = None
            task.status = TaskStatus.WAITING
        return server       


async def schedule_waiting_tasks(db: AsyncSession, batch_size: int = 100) -> int:
    async with db.begin():
        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.WAITING)
            .order_by(Task.created_at.asc(), Task.uid.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        waiting_tasks = list(result.scalars().all())
        scheduled_count = 0
        for task in waiting_tasks:
            class _Payload:
                cpu_req = task.cpu_req
                ram_req = task.ram_req
                gpu_req = task.gpu_req
                policy = PolicyType.BEST_FIT
            result_s = await db.execute(
                build_server_candidate_stmt(_Payload).where(Server.status == ServerStatus.RUNNING)
            )
            server = result_s.scalar_one_or_none()
            if server is None:
                continue
            server.cpu_free -= task.cpu_req
            server.ram_free -= task.ram_req
            server.gpu_free -= task.gpu_req
            task.server_uid = server.uid
            task.status = TaskStatus.RUNNING
            scheduled_count += 1
        return scheduled_count