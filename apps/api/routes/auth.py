from fastapi import APIRouter

router = APIRouter()

@router.post("/login")
def login():
    return {"accessToken": "mock.jwt.token", "expiresIn": 3600}

@router.post("/refresh")
def refresh():
    return {"accessToken": "mock.jwt.token2", "expiresIn": 3600}

@router.post("/logout")
def logout():
    return {"ok": True}
