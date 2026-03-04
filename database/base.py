from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime
from sqlalchemy.orm import declarative_base, Mapped
from typing import Self
from ksuid import ksuid


def new_ksuid() -> str:
    return str(ksuid())


DeclarativeBase = declarative_base()


class BaseEntity(DeclarativeBase):
    __abstract__ = True
    uid: Mapped[str] = Column(String(50), primary_key=True, default=new_ksuid)

    _public_fields: set[str] = {"uid"}

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def apply_patch(self, patch_obj: Self):
        for key, value in patch_obj.__dict__.items():
            if (
                not key.startswith("_")
                and hasattr(self, key)
                and key in self._public_fields
            ):
                setattr(self, key, value)

    @staticmethod
    def from_dict(data: dict):
        raise NotImplementedError()