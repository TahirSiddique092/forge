from pydantic import BaseModel

class UpdateStatusPayload(BaseModel):
    installation_id: int
    repo: str
    check_run_id: int
    success: bool
    
class CreateStepPayload(BaseModel):
    name: str

class FinishStepPayload(BaseModel):
    status: str
    stdout: str = ""
    stderr: str = ""