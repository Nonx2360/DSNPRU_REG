from sqlalchemy.orm import Session
from fastapi import Request
from . import models

def log_action(db: Session, admin_username: str, action: str, details: str = None, request: Request = None):
    ip = request.client.host if request else None
    log = models.AdminLog(
        admin_username=admin_username,
        action=action,
        details=details,
        ip_address=ip
    )
    db.add(log)
    db.commit()
