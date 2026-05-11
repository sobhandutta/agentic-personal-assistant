# Google OAuth is disabled in this deployment.
from .base_agent import BaseAgent


class DriveAgent(BaseAgent):
    """Disabled — Google Drive requires OAuth which is not available in this deployment."""

    def run(self, question: str) -> str:
        return "[DriveAgent] Google Drive is not available in this deployment."
