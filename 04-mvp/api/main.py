"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api.db import init_db
from api.middleware.auth import auth_middleware
from api.routes.stocks import router as stocks_router
from api.routes.events import router as events_router
from api.routes.search import router as search_router
from api.routes.factors import router as factors_router
from api.routes.health import router as health_router
from api.routes.schedule import router as schedule_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    print("Database initialized. Server ready.")
    yield


app = FastAPI(
    title="A股全量信息检索知识库",
    description="个股事件链、全文搜索、因子数据、系统监控",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.middleware("http")(auth_middleware)

# Include routers
app.include_router(stocks_router)
app.include_router(events_router)
app.include_router(search_router)
app.include_router(factors_router)
app.include_router(health_router)
app.include_router(schedule_router)

# Serve static files (frontend)
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="static")
