from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from .database import Base, engine, SessionLocal
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
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/activities")
    async def activities_page(request: Request):
        return templates.TemplateResponse("activities.html", {"request": request})

    @app.get("/about")
    async def about_page(request: Request):
        return templates.TemplateResponse("about.html", {"request": request})

    @app.get("/admin/login")
    async def admin_login_page(request: Request):
        return templates.TemplateResponse("admin_login.html", {"request": request})

    @app.get("/admin/dashboard")
    async def admin_dashboard_page(request: Request):
        return templates.TemplateResponse("admin_dashboard.html", {"request": request})

    @app.get("/admin/activities")
    async def admin_activities_page(request: Request):
        return templates.TemplateResponse("admin_activities.html", {"request": request})

    @app.get("/admin/activity/{activity_id}")
    async def admin_activity_detail_page(request: Request, activity_id: int):
        return templates.TemplateResponse(
            "admin_activity_detail.html", {"request": request, "activity_id": activity_id}
        )

    @app.get("/admin/export")
    async def admin_export_page(request: Request):
        return templates.TemplateResponse("admin_export.html", {"request": request})

    @app.get("/admin/students")
    async def admin_students_page(request: Request):
        return templates.TemplateResponse("admin_students.html", {"request": request})

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

@app.on_event("startup")
async def startup_event():
    logger = logging.getLogger("uvicorn")
    logger.info("Application startup: DSNPRU_REG Activity Registration API started")

@app.on_event("shutdown")
async def shutdown_event():
    logger = logging.getLogger("uvicorn")
    logger.info("Application shutdown")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("uvicorn")
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# Additional Admin Page Routes

@app.get("/admin/logs")
async def admin_logs_page(request: Request):
    return templates.TemplateResponse("admin_logs.html", {"request": request})

@app.get("/admin/users")
async def admin_users_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})
