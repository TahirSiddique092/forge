from pydantic import BaseModel
from typing import Optional, Dict

class ProjectCommands(BaseModel):
    install: str
    build: str
    test: Optional[str] = None

class ProjectSpec(BaseModel):
    runtime: str                # node, python
    runtime_version: str        # 20, 3.11
    framework: str              # react, nextjs
    tool: str                   # vite, next
    commands: ProjectCommands

class CreateProjectRequest(BaseModel):
    name: str
    spec: ProjectSpec
