class TesterService:
    async def run(self, *, workspace_path: str, test_plan: dict) -> dict:
        return {"status": "passed", "workspace_path": workspace_path, "test_plan": test_plan}
