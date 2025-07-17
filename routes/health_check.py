from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["starter"])

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "All services working fine"}
