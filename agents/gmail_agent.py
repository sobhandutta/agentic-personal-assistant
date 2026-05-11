# Google OAuth is disabled in this deployment.
from .base_agent import BaseAgent


class GmailAgent(BaseAgent):
    """Disabled — Gmail requires OAuth which is not available in this deployment."""

    def run(self, question: str) -> str:
        return "[GmailAgent] Gmail is not available in this deployment."
