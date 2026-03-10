import asyncio
from typing import AsyncIterator

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
import asyncpg


@pytest_asyncio.fixture(autouse=True, scope="function")
async def clean_db() -> None:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("TRUNCATE TABLE tasks, servers RESTART IDENTITY CASCADE")
    finally:
        await conn.close()
    yield

@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url="http://localhost:8000") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_and_db_ping(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    
    resp = await client.get("/db-ping")
    assert resp.status_code == 200
    assert resp.json() == {"result": 1}


@pytest.mark.asyncio
async def test_server_create_and_list(client: AsyncClient) -> None:
    payload = {"cpu_total": 4, "ram_total": 8, "gpu_total": 1}
    resp = await client.post("/servers", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "uid" in data and isinstance(data["uid"], str)
    assert data["cpu_total"] == payload["cpu_total"]
    assert data["ram_total"] == payload["ram_total"]
    assert data["gpu_total"] == payload["gpu_total"]
    assert data["cpu_free"] == payload["cpu_total"]
    assert data["ram_free"] == payload["ram_total"]
    assert data["gpu_free"] == payload["gpu_total"]
    assert "created_at" in data
    resp = await client.get("/servers")
    assert resp.status_code == 200
    servers = resp.json()
    assert isinstance(servers, list) and len(servers) == 1
    listed = servers[0]
    assert listed["uid"] == data["uid"]
    assert listed["cpu_free"] == data["cpu_free"]
    assert listed["ram_free"] == data["ram_free"]
    assert listed["gpu_free"] == data["gpu_free"]


@pytest.mark.asyncio
async def test_task_placement_first_fit(client: AsyncClient) -> None:
    s1 = {"cpu_total": 4, "ram_total": 4, "gpu_total": 0}
    s2 = {"cpu_total": 8, "ram_total": 8, "gpu_total": 0}
    resp1 = await client.post("/servers", json=s1)
    resp2 = await client.post("/servers", json=s2)
    assert resp1.status_code == 201 and resp2.status_code == 201
    uid1 = resp1.json()["uid"]
    uid2 = resp2.json()["uid"]

    task_payload = {"cpu_req": 3, "ram_req": 2, "gpu_req": 0, "policy": "FIRST_FIT"}
    resp_t1 = await client.post("/tasks", json=task_payload)
    assert resp_t1.status_code == 201
    task1 = resp_t1.json()
    resp_t2 = await client.post("/tasks", json=task_payload)
    assert resp_t2.status_code == 201
    task2 = resp_t2.json()
    
    assert task1["server_uid"] == uid1
    assert task2["server_uid"] == uid2

    resp = await client.get("/servers")
    servers = {srv["uid"]: srv for srv in resp.json()}

    srv1 = servers[uid1]
    assert srv1["cpu_free"] == 1
    assert srv1["ram_free"] == 2

    srv2 = servers[uid2]
    assert srv2["cpu_free"] == 5
    assert srv2["ram_free"] == 6


@pytest.mark.asyncio
async def test_task_placement_best_fit(client: AsyncClient) -> None:
    s1 = {"cpu_total": 4, "ram_total": 4, "gpu_total": 0}
    s2 = {"cpu_total": 6, "ram_total": 5, "gpu_total": 0}
    resp1 = await client.post("/servers", json=s1)
    resp2 = await client.post("/servers", json=s2)
    uid1 = resp1.json()["uid"]
    uid2 = resp2.json()["uid"]

    task_a = {"cpu_req": 1, "ram_req": 2, "gpu_req": 0}
    task_b = {"cpu_req": 2, "ram_req": 2, "gpu_req": 0}
    task_c = {"cpu_req": 1, "ram_req": 1, "gpu_req": 0}
    
    res_a = await client.post("/tasks", json=task_a)
    res_b = await client.post("/tasks", json=task_b)
    res_c = await client.post("/tasks", json=task_c)
    assert res_a.status_code == res_b.status_code == res_c.status_code == 201
    t_a = res_a.json()
    t_b = res_b.json()
    t_c = res_c.json()
    
    assert t_a["server_uid"] == uid1
    assert t_b["server_uid"] == uid1
    assert t_c["server_uid"] == uid2
    resp = await client.get("/servers")
    servers = {srv["uid"]: srv for srv in resp.json()}

    srv1 = servers[uid1]
    assert srv1["cpu_free"] == 1
    assert srv1["ram_free"] == 0

    srv2 = servers[uid2]
    assert srv2["cpu_free"] == 5
    assert srv2["ram_free"] == 4


@pytest.mark.asyncio
async def test_no_capacity_conflict(client: AsyncClient) -> None:
    srv_payload = {"cpu_total": 2, "ram_total": 2, "gpu_total": 0}
    srv_resp = await client.post("/servers", json=srv_payload)
    assert srv_resp.status_code == 201

    task_ok = {"cpu_req": 1, "ram_req": 2, "gpu_req": 0}
    resp_ok = await client.post("/tasks", json=task_ok)
    assert resp_ok.status_code == 201

    task_conflict = {"cpu_req": 2, "ram_req": 1, "gpu_req": 0}
    resp_conflict = await client.post("/tasks", json=task_conflict)
    assert resp_conflict.status_code == 409
    assert resp_conflict.json()["detail"] == "No capacity on any server"


@pytest.mark.asyncio
async def test_task_expiry(client: AsyncClient) -> None:
    from app.service import expire_due_tasks
    from database.session import AsyncSessionLocal


    srv_payload = {"cpu_total": 4, "ram_total": 4, "gpu_total": 0}
    srv_resp = await client.post("/servers", json=srv_payload)
    assert srv_resp.status_code == 201
    srv_uid = srv_resp.json()["uid"]

    ttl_task = {"cpu_req": 1, "ram_req": 1, "gpu_req": 0, "ttl_seconds": 1}
    res1 = await client.post("/tasks", json=ttl_task)
    res2 = await client.post("/tasks", json=ttl_task)
    assert res1.status_code == res2.status_code == 201

    tasks_before = (await client.get("/tasks")).json()
    assert all(t["status"] == "RUNNING" for t in tasks_before)

    await asyncio.sleep(1.5)

    async with AsyncSessionLocal() as session:
        expired_count = await expire_due_tasks(session, batch_size=100)
        assert expired_count == 2
        await session.commit()

    tasks_after = (await client.get("/tasks")).json()
    assert all(t["status"] == "EXPIRED" for t in tasks_after)
    servers = {srv["uid"]: srv for srv in (await client.get("/servers")).json()}
    srv = servers[srv_uid]
    assert srv["cpu_free"] == srv["cpu_total"]
    assert srv["ram_free"] == srv["ram_total"]
