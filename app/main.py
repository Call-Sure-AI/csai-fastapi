from fastapi import FastAPI
from routes.health_check import router as health_check_router
from routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Callsure AI - Fast API", description="A FastAPI project for Callsure AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],  
)

app.include_router(health_check_router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Starter!", "status": "running"}