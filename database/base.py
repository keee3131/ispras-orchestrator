
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ksuid import ksuid


def new_ksuid() -> str:
    return str(ksuid())


class Base(DeclarativeBase):
    pass


class BaseEntity(Base):
    __abstract__ = True

    uid: Mapped[str] = mapped_column(String(50), primary_key=True, default=new_ksuid)