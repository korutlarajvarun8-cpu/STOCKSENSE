"""
StockSense FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.redis import get_redis, close_redis
import app.models  # noqa: F401 — imports all models for Alembic

# Import all routers
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.warehouse import (
    wh_router, loc_router, sup_router, cust_router
)
from app.api.v1.endpoints.operations import (
    po_router, rec_router, so_router, del_router, trf_router, adj_router
)
from app.api.v1.endpoints.tracking import (
    batch_router, serial_router, reorder_router
)
from app.api.v1.endpoints.dashboard import (
    dash_router, ledger_router, report_router, notif_router,
    ws_router, ai_router, users_router, search_router, val_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    # Startup
    print("StockSense starting up...")
    # Initialize Redis
    await get_redis()
    print("Redis connected")

    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    yield

    # Shutdown
    await close_redis()
    print("StockSense shutting down...")


app = FastAPI(
    title="StockSense API",
    description="AI-Powered Inventory Management System",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─── Global Error Handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "trace": traceback.format_exc()},
        )
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})


# ─── Routes ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api"

app.include_router(auth_router, prefix=f"{API_PREFIX}")
app.include_router(products_router, prefix=f"{API_PREFIX}")
app.include_router(wh_router, prefix=f"{API_PREFIX}")
app.include_router(loc_router, prefix=f"{API_PREFIX}")
app.include_router(sup_router, prefix=f"{API_PREFIX}")
app.include_router(cust_router, prefix=f"{API_PREFIX}")
app.include_router(po_router, prefix=f"{API_PREFIX}")
app.include_router(rec_router, prefix=f"{API_PREFIX}")
app.include_router(so_router, prefix=f"{API_PREFIX}")
app.include_router(del_router, prefix=f"{API_PREFIX}")
app.include_router(trf_router, prefix=f"{API_PREFIX}")
app.include_router(adj_router, prefix=f"{API_PREFIX}")
app.include_router(batch_router, prefix=f"{API_PREFIX}")
app.include_router(serial_router, prefix=f"{API_PREFIX}")
app.include_router(reorder_router, prefix=f"{API_PREFIX}")
app.include_router(dash_router, prefix=f"{API_PREFIX}")
app.include_router(ledger_router, prefix=f"{API_PREFIX}")
app.include_router(report_router, prefix=f"{API_PREFIX}")
app.include_router(notif_router, prefix=f"{API_PREFIX}")
app.include_router(ai_router, prefix=f"{API_PREFIX}")
app.include_router(users_router, prefix=f"{API_PREFIX}")
app.include_router(search_router, prefix=f"{API_PREFIX}")
app.include_router(val_router, prefix=f"{API_PREFIX}")
app.include_router(ws_router)  # WebSocket at /ws


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "app": "StockSense", "version": "1.0.0"}


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/api/docs")


# ─── Static Files ─────────────────────────────────────────────────────────────

if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
