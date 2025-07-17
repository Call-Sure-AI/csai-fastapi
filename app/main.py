from fastapi import FastAPI
from routes.health_check import router as health_check_router

app = FastAPI(title="Callsure AI - Fast API", description="A FastAPI project for Callsure AI")

app.include_router(health_check_router)

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Starter!", "status": "running"}