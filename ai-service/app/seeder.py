from typing import Dict, Any

def seed_sample_notices_if_empty() -> Dict[str, Any]:
    """
    Disabled: Documents are only loaded when explicitly uploaded by the user.
    """
    return {"status": "disabled", "message": "Pre-stored notices disabled. Upload documents manually."}
