from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """All sub-agents implement this interface."""

    @abstractmethod
    def run(self, question: str) -> str:
        """Answer a natural-language question and return a string result."""
        ...
