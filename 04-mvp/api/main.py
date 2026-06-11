"""FastAPI主应用。

A股全量信息检索知识库 — 三层数据湖架构
"""
import os
import sys
import time
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.middleware.auth import require_auth
from api.routes import stocks, events, search, factors, health, schedule
from api.db import init_db, get_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/api.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# 启动/关闭事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("=== A股知识库API启动 ===")
    init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("=== A股知识库API关闭 ===")


# 创建应用
app = FastAPI(
    title="A股全量信息检索知识库",
    description="三层数据湖架构：Bronze(原始不可变) → Silver(清洗统一) → Gold(因子+ML)",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS配置（生产环境应限制来源）
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流配置
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获，避免暴露敏感信息。"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求。"""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
    )
    return response


# 注册路由
app.include_router(health.router, tags=["健康检查"])
app.include_router(stocks.router, tags=["股票查询"])
app.include_router(events.router, tags=["事件链"], dependencies=[require_auth])
app.include_router(search.router, tags=["全文搜索"])
app.include_router(factors.router, tags=["因子数据"], dependencies=[require_auth])
app.include_router(schedule.router, tags=["ETL调度"], dependencies=[require_auth])

# 静态文件挂载（前端）
if os.path.exists("web"):
    app.mount("/", StaticFiles(directory="web", html=True), name="static")


# 根路由
@app.get("/")
async def root():
    """根路由重定向到前端。"""
    return {"message": "A股全量信息检索知识库API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    os.makedirs("logs", exist_ok=True)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
