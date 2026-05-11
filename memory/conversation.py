from config import MAX_MEMORY_TURNS


class ConversationMemory:
    """
    Converts Gradio chat history (list of [user, assistant] pairs) into the
    Anthropic messages format and trims to MAX_MEMORY_TURNS to stay within
    the context window.

    Learning note: this demonstrates the short-term memory pattern — every
    request carries the recent conversation so the model can resolve follow-ups.
    """

    def to_messages(self, gradio_history: list) -> list[dict]:
        """
        Gradio 5+ passes history as [{"role": ..., "content": ...}, ...].
        Older Gradio passed [[user_msg, assistant_msg], ...].
        Convert either format to Anthropic's messages format and trim to MAX_MEMORY_TURNS.
        """
        if not gradio_history:
            return []

        # Gradio 5+ format: list of dicts with "role" and "content"
        if isinstance(gradio_history[0], dict):
            trimmed = gradio_history[-(MAX_MEMORY_TURNS * 2):]
            return [
                {"role": m["role"], "content": m["content"]}
                for m in trimmed
                if m.get("content")
            ]

        # Legacy Gradio format: [[user_msg, assistant_msg], ...]
        trimmed = gradio_history[-MAX_MEMORY_TURNS:]
        messages = []
        for user_msg, assistant_msg in trimmed:
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg})
        return messages
