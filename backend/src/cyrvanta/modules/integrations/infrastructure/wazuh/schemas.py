from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WazuhHit(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: str = Field(alias="_index")
    document_id: str = Field(alias="_id")
    source: dict[str, Any] = Field(alias="_source")
    sort: list[str | int | float] | None = None


class WazuhSearchResponse(BaseModel):
    hits: list[WazuhHit]

    @classmethod
    def from_opensearch(cls, payload: dict[str, Any]) -> "WazuhSearchResponse":
        raw_hits = payload.get("hits", {})
        values = raw_hits.get("hits", []) if isinstance(raw_hits, dict) else []
        return cls(hits=[WazuhHit.model_validate(item) for item in values])
