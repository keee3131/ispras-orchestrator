from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from database.models import TaskStatus, PolicyType, ServerStatus


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
    status: ServerStatus
    created_at: datetime


class TaskCreate(BaseModel):
    cpu_req: int = Field(ge=0)
    ram_req: int = Field(ge=0)
    gpu_req: int = Field(ge=0)
    ttl_seconds: Optional[int] = Field(default=None, gt=0)
    policy: Optional[PolicyType] = PolicyType.BEST_FIT


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    cpu_req: int
    ram_req: int
    gpu_req: int
    status: TaskStatus
    created_at: datetime
    expires_at: Optional[datetime] = None   
    server_uid: Optional[str] = None
