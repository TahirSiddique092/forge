import uuid

def generate_project_id():
    return f"proj_{uuid.uuid4().hex[:8]}"
