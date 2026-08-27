from typing import Any, Self

import pytoml
import yaml
from pydantic import BaseModel

__all__ = ("BaseStruct",)


class BaseStruct(BaseModel):
    """Base data structure for all schemas."""

    def to_dict(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_unset: bool = False,
    ) -> dict[str, Any]:

        return self.model_dump(
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
        )

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> Self:

        return cls.model_validate(obj)

    def to_json(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_unset: bool = False,
    ) -> str:

        return self.model_dump_json(
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
        )

    @classmethod
    def from_json(cls, obj: str) -> Self:

        return cls.model_validate_json(obj)

    @classmethod
    def from_yaml(cls, obj: str) -> Self:

        return cls.model_validate(yaml.safe_load(obj))

    @classmethod
    def from_toml(cls, obj: str) -> Self:

        return cls.model_validate(pytoml.loads(obj))
