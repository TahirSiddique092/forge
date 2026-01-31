from pydantic import BaseModel
from typing import Optional, Dict

class ProjectCommands(BaseModel):
    install: str
    build: str
    test: Optional[str] = None

class ProjectSpec(BaseModel):
    runtime: str                
    runtime_version: str        
    framework: str             
    tool: str                  
    commands: ProjectCommands

class CreateProjectRequest(BaseModel):
    name: str
    spec: ProjectSpec
