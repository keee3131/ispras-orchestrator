from enum import StrEnum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import BaseEntity


class TaskStatus(StrEnum):
    RUNNING = "RUNNING"
    EXPIRED = "EXPIRED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    
class PolicyType(StrEnum):
    FIRST_FIT = "FIRST_FIT"
    BEST_FIT = "BEST_FIT"


class Server(BaseEntity):
    __tablename__ = "servers"

    cpu_total: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_total: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_total: Mapped[int] = mapped_column(Integer, nullable=False)

    cpu_free: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_free: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_free: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tasks: Mapped[list["Task"]] = relationship(back_populates="server")

    __table_args__ = (
        CheckConstraint("cpu_total >= 0", name="ck_server_cpu_total_nonneg"),
        CheckConstraint("ram_total >= 0", name="ck_server_ram_total_nonneg"),
        CheckConstraint("gpu_total >= 0", name="ck_server_gpu_total_nonneg"),
        CheckConstraint("cpu_free >= 0 AND cpu_free <= cpu_total", name="ck_server_cpu_free"),
        CheckConstraint("ram_free >= 0 AND ram_free <= ram_total", name="ck_server_ram_free"),
        CheckConstraint("gpu_free >= 0 AND gpu_free <= gpu_total", name="ck_server_gpu_free"),
    )


class Task(BaseEntity):
    __tablename__ = "tasks"

    cpu_req: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_req: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_req: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.RUNNING
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    server_uid: Mapped[int | None] = mapped_column(ForeignKey("servers.uid"), nullable=True)
    server: Mapped[Server | None] = relationship(back_populates="tasks")

    __table_args__ = (
        CheckConstraint("cpu_req >= 0", name="ck_task_cpu_req_nonneg"),
        CheckConstraint("ram_req >= 0", name="ck_task_ram_req_nonneg"),
        CheckConstraint("gpu_req >= 0", name="ck_task_gpu_req_nonneg"),
        Index("ix_tasks_status_expires_at", "status", "expires_at"),
    )
