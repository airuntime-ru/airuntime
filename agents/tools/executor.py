class ToolExecutorService:
    """Backend tool gateway; never forward raw secrets to LLM prompts."""

    async def call(self, *, name: str, args: dict, actor_id: str) -> dict:
        return {"tool": name, "args": args, "actor_id": actor_id, "status": "ok"}
