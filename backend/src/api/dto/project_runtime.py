from pydantic import BaseModel


class ProjectRuntimeLimitsResponse(BaseModel):
    running: int
    max_running: int
