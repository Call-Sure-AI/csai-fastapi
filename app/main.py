from fastapi import FastAPI, Request
from routes.health_check import router as health_check_router
from routes.auth import router as auth_router
from routes.agent import router as agent_router
from routes.company import router as company_router
#from routes.conversation import conversation_router
#from routes.customer import customer_router
from routes.email import router as email_router
from routes.invitation import router as invitation_router
from routes.s3 import router as s3_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging
import os
from typing import Dict, Any

# Import the centralized router
from routes import api_router
from app.db.postgres_client import postgres_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Application metadata
APP_NAME = "Callsure AI Voice System"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = """
AI-powered voice calling system for customer service.

## Features
* Real-time voice processing
* Multi-agent support
* Customer context management
* Call recording and analytics
"""

# Get environment
ENV = os.getenv('FLASK_ENV', 'development')
IS_PRODUCTION = ENV == 'production'

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"Starting {APP_NAME} v{APP_VERSION} in {ENV} mode...")
    
    try:
        # Initialize database connection pool
        await postgres_client.initialize()
        logger.info("✅ Database connection pool initialized")
        
        # Check database connectivity
        pool_stats = await postgres_client.client.get_pool_stats()
        logger.info(f"📊 Database pool stats: {pool_stats}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {APP_NAME}...")
    
    try:
        # Close database connections
        await postgres_client.close()
        logger.info("✅ Database connections closed")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

# Create FastAPI instance
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
allowed_origins = ["*"]  # Allow all in development
if IS_PRODUCTION:
    allowed_origins = [
        "http://localhost:3000",
        "https://callsure.ai",
        "https://*.callsure.ai",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(health_check_router)
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(company_router)
#app.include_router(customer_router)
app.include_router(email_router)
app.include_router(invitation_router)
app.include_router(s3_router)

# Add trusted host middleware for security in production
if IS_PRODUCTION:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "api.callsure.ai",
            "*.callsure.ai",
        ]
    )

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time to headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    
    # Log slow requests (>1s for voice system)
    if process_time > 1.0:
        logger.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {process_time:.3f}s"
        )
    
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "path": str(request.url.path),
        }
    )

# Include API routes
app.include_router(api_router, prefix="/api")

# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with system status"""
    try:
        # Get database stats
        pool_stats = await postgres_client.client.get_pool_stats()
        
        # Test database latency
        start = time.time()
        await postgres_client.client.execute_query_one("SELECT 1", timeout=1.0)
        db_latency_ms = (time.time() - start) * 1000
        
        return {
            "service": APP_NAME,
            "version": APP_VERSION,
            "status": "operational",
            "environment": ENV,
            "database": {
                "connected": True,
                "latency_ms": round(db_latency_ms, 2),
                "pool": pool_stats,
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": APP_NAME,
            "version": APP_VERSION,
            "status": "degraded",
            "environment": ENV,
            "database": {
                "connected": False,
                "error": str(e)
            }
        }

# Voice system specific health endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Detailed health check for voice system monitoring"""
    health_status = {
        "status": "healthy",
        "checks": {},
        "metadata": {
            "version": APP_VERSION,
            "environment": ENV,
            "timestamp": time.time(),
        }
    }
    
    # Database health check
    try:
        start = time.time()
        result = await postgres_client.client.execute_query_one(
            "SELECT COUNT(*) as agent_count FROM agents WHERE is_active = true",
            timeout=2.0
        )
        db_latency_ms = (time.time() - start) * 1000
        
        pool_stats = await postgres_client.client.get_pool_stats()
        
        health_status["checks"]["database"] = {
            "status": "pass" if db_latency_ms < 100 else "warn",
            "latency_ms": round(db_latency_ms, 2),
            "active_agents": result["agent_count"] if result else 0,
            "pool": pool_stats,
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "fail",
            "error": str(e)
        }
    
    return health_status

# Metrics endpoint (for Prometheus, etc.)
@app.get("/metrics", tags=["Monitoring"])
async def metrics() -> str:
    """Prometheus-compatible metrics endpoint"""
    try:
        pool_stats = await postgres_client.client.get_pool_stats()
        
        metrics_data = [
            f'# HELP db_pool_size Current size of the database connection pool',
            f'# TYPE db_pool_size gauge',
            f'db_pool_size {pool_stats.get("size", 0)}',
            f'',
            f'# HELP db_pool_free Free connections in the pool',
            f'# TYPE db_pool_free gauge', 
            f'db_pool_free {pool_stats.get("free_connections", 0)}',
            f'',
            f'# HELP db_pool_used Used connections in the pool',
            f'# TYPE db_pool_used gauge',
            f'db_pool_used {pool_stats.get("used_connections", 0)}',
        ]
        
        return "\n".join(metrics_data)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return "# Error generating metrics\n"

# Development only routes
if not IS_PRODUCTION:
    @app.get("/debug/routes", tags=["Debug"])
    async def debug_routes():
        """List all registered routes (development only)"""
        routes = []
        for route in app.routes:
            if hasattr(route, "methods"):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": route.name,
                })
        return {"total_routes": len(routes), "routes": routes}

# Startup message
@app.on_event("startup")
async def startup_message():
    """Print startup information"""
    logger.info(f"""
    🚀 {APP_NAME} Started!
    📍 Environment: {ENV}
    🌐 API Docs: http://localhost:8000/api/docs
    📊 Metrics: http://localhost:8000/metrics
    💚 Health: http://localhost:8000/health
    """)

# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not IS_PRODUCTION,
        log_level="info",
        access_log=True,
        workers=1 if not IS_PRODUCTION else 4,
    )