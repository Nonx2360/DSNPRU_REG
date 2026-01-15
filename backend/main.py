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
    app = FastAPI(title="SIC Day Activity Registration API", version="1.0.0")

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
    app.include_router(public.router, prefix="", tags=["public"])
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


app = create_app()
