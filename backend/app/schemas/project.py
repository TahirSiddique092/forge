from pydantic import BaseModel
from typing import Optional, Dict, List

class ComponentSpec(BaseModel):
    name: str                
    root_dir: str             
    platform: str             
    runtime: str            
    install_command: str       
    test_command: Optional[str] = None
    build_command: str        
    env_vars: Dict[str, str] = {}

class CreateProjectRequest(BaseModel):
    name: str
    components: List[ComponentSpec] 