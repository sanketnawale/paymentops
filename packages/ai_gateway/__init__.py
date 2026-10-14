"""AI gateway boundary (non-authoritative).

Responsibilities (planned): provider abstraction over Ollama / vLLM / customer-approved
providers for *explanations and candidate suggestions only*. It is forbidden for AI to be
authoritative for validation or to approve/execute financial actions (rules #4, #5). The
product must function with AI disabled (rule #6). No provider logic in Week 1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AISuggestion:
    """An AI candidate. Never a decision; always requires deterministic re-validation."""

    text: str
    confidence: float | None = None


class IAIProvider(ABC):
    @abstractmethod
    def supports(self, feature: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def suggest(self, prompt: str) -> AISuggestion:
        raise NotImplementedError
