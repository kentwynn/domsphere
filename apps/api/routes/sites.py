from fastapi import APIRouter
import uuid

router = APIRouter()

@router.post("/register")
def register_site():
    return {
        "siteId": str(uuid.uuid4()),
        "siteKey": "sk_mock_new_site",
        "createdAt": "2025-08-18T00:00:00Z",
        "status": "active"
    }

@router.get("/{site_id}")
def get_site(site_id: str):
    return {
        "siteId": site_id,
        "name": "Mock Site",
        "status": "active",
        "createdAt": "2025-08-01T00:00:00Z"
    }

@router.delete("/{site_id}")
def delete_site(site_id: str):
    return {"siteId": site_id, "deleted": True}
