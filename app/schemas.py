from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from database.models import TaskStatus


class ServerCreate(BaseModel):
    cpu_total: int = Field(ge=0)
    ram_total: int = Field(ge=0)
    gpu_total: int = Field(ge=0)


class ServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    cpu_total: int
    ram_total: int
    gpu_total: int
    cpu_free: int
    ram_free: int
    gpu_free: int
    created_at: datetime


class TaskCreate(BaseModel):
    cpu_req: int = Field(ge=0)
    ram_req: int = Field(ge=0)
    gpu_req: int = Field(ge=0)
    ttl_seconds: int | None = Field(default=None, gt=0)
    policy: Literal["first_fit", "best_fit"] = "best_fit"


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    cpu_req: int
    ram_req: int
    gpu_req: int
    status: TaskStatus
    created_at: datetime
    expires_at: datetime | None
    server_uid: str | None