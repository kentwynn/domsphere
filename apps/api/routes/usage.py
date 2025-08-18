from fastapi import APIRouter, Query

router = APIRouter()

@router.get("")
def get_usage(
    siteId: str,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None
):
    return {
        "siteId": siteId,
        "window": {"from": from_, "to": to},
        "calls": 123,
        "tokens": 4567,
        "cacheHits": 42
    }
