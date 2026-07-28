from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExplanationDraft:
    text_es: str
    text_en: str
    provider: str
    model: str


class AIProvider(Protocol):
    async def redact_explanation(
        self, deterministic_es: str, deterministic_en: str
    ) -> ExplanationDraft | None: ...
