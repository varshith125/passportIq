"""Base schema model supporting Pydantic v2 natively with runtime compatibility."""

from __future__ import annotations

from typing import Any

import pydantic
from pydantic import BaseModel

PYDANTIC_V2 = int(pydantic.__version__.split(".")[0]) >= 2

if PYDANTIC_V2:
    from pydantic import ConfigDict  # type: ignore[attr-defined]


class SchemaModel(BaseModel):
    """Base model configured for strict extra-field rejection and v2 serialization."""

    if PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", populate_by_name=True)
    else:

        class Config:
            extra = "forbid"
            allow_population_by_field_name = True

        def model_dump(self, **kwargs: Any) -> dict[str, Any]:
            """Provide Pydantic v2 model_dump() when running under Pydantic v1."""
            return self.dict(**kwargs)
