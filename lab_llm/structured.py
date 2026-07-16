"""Small, versioned contracts for structured model output."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class OutputContract(Generic[OutputT]):
    """One versioned JSON Schema and its corresponding Python type."""

    name: str
    version: str
    output_type: type[OutputT]

    @property
    def contract_id(self) -> str:
        """Stable, human-readable identifier saved with each result."""
        return f"{self.name}@{self.version}"

    @property
    def output_format(self) -> dict[str, Any]:
        """Responses API ``text.format`` value for this contract."""
        return {
            "type": "json_schema",
            "name": f"{self.name}_v{self.version}",
            "strict": True,
            "schema": self.output_type.model_json_schema(),
        }

    def parse(self, text: str) -> OutputT:
        """Parse JSON text into the declared Pydantic type."""
        return self.output_type.model_validate_json(text)
