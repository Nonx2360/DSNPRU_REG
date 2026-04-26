from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import Base, engine, SessionLocal
from .websocket_manager import manager
from .routers import public, admin, export
from .auth import get_password_hash
from . import models


templates = Jinja2Templates(directory="frontend/templates")


def create_app() -> FastAPI:
    app = FastAPI(title="DSNPRU_REG Activity Registration API", version="1.0.0")

    # CORS (allow frontend on same origin or localhost variants)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create DB tables
    Base.metadata.create_all(bind=engine)

    # Seed default admin if none exists
    with SessionLocal() as db:
        if not db.query(models.Admin).first():
            default_admin = models.Admin(
                username="admin",
                password_hash=get_password_hash("admin123"),
                is_superuser=True,
            )
            db.add(default_admin)
            db.commit()

    # Routers
    app.include_router(public.router, prefix="/api", tags=["public"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(export.router, prefix="/export", tags=["export"])

    # Static files
    app.mount(
        "/static",
        StaticFiles(directory="frontend/static"),
        name="static",
    )

    # Simple page routes returning templates (optional; frontend can also be served by static server)

    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/activities")
    async def activities_page(request: Request):
        return templates.TemplateResponse(request=request, name="activities.html")

    @app.get("/about")
    async def about_page(request: Request):
        return templates.TemplateResponse(request=request, name="404.html")

    @app.get("/admin/login")
    async def admin_login_page(request: Request):
        return templates.TemplateResponse(request=request, name="admin_login.html")

    @app.get("/admin/dashboard")
    async def admin_dashboard_page(request: Request):
        return templates.TemplateResponse(request=request, name="admin_dashboard.html")

    @app.get("/admin/activities")
    async def admin_activities_page(request: Request):
        return templates.TemplateResponse(request=request, name="admin_activities.html")

    @app.get("/admin/activity/{activity_id}")
    async def admin_activity_detail_page(request: Request, activity_id: int):
        return templates.TemplateResponse(
            request=request, name="admin_activity_detail.html", context={"activity_id": activity_id}
        )

    @app.get("/admin/export")
    async def admin_export_page(request: Request):
        return templates.TemplateResponse(request=request, name="admin_export.html")

    @app.get("/admin/students")
    async def admin_students_page(request: Request):
        return templates.TemplateResponse(request=request, name="admin_students.html")

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        accepts_html = "text/html" in request.headers.get("accept", "").lower()
        if accepts_html and exc.status_code in {401, 403, 404}:
            return templates.TemplateResponse(
                request=request,
                name="404.html",
                status_code=404,
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.websocket("/ws/activities")
    async def websocket_activities(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


# Configure logging
import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")
handler = RotatingFileHandler("app.log", maxBytes=1000000, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

app = create_app()

import os
import time
import asyncio

@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger("uvicorn")
    logger.info("Application startup: DSNPRU_REG Activity Registration API started")
    asyncio.create_task(log_system_metrics())

async def log_system_metrics():
    while True:
        try:
            with SessionLocal() as db:
                # DB Size
                db_path = "sicday.db"
                if os.path.exists(db_path):
                    size = os.path.getsize(db_path)
                    db.add(models.SystemMetric(metric_type="db_size", value=size))
                
                # DB Health (Simple check)
                db.execute(models.Base.metadata.tables['students'].select().limit(1))
                db.add(models.SystemMetric(metric_type="db_health", status="healthy"))
                db.commit()
        except Exception as e:
            logging.error(f"Error logging metrics: {e}")
        await asyncio.sleep(300) # Every 5 minutes

@app.on_event("shutdown")
async def shutdown_event():
    logger = logging.getLogger("uvicorn")
    logger.info("Application shutdown")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = int((time.perf_counter() - start_time) * 1000)
    
    # Don't log static files or heartbeats to keep DB clean if many
    if not request.url.path.startswith("/static"):
        try:
            with SessionLocal() as db:
                log = models.RequestLog(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    response_time_ms=process_time
                )
                db.add(log)
                db.commit()
        except Exception as e:
            logging.error(f"Error logging request to DB: {e}")

    return response


# Additional Admin Page Routes

@app.get("/admin/logs")
async def admin_logs_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_logs.html")

@app.get("/admin/users")
async def admin_users_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_users.html")

@app.get("/admin/analytics")
async def admin_analytics_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_analytics.html")

@app.get("/admin/announcements")
async def admin_announcements_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_announcements.html")

@app.get("/admin/platform/status")
async def admin_platform_status_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_status.html")
