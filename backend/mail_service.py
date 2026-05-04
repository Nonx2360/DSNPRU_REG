import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from .env_settings import get_mail_settings, mail_settings_complete


logger = logging.getLogger(__name__)


def waitlist_mail_ready() -> bool:
    return mail_settings_complete(get_mail_settings())


def build_mail_config() -> ConnectionConfig | None:
    settings = get_mail_settings()
    if not mail_settings_complete(settings):
        return None

    port = int(settings["MAIL_PORT"])
    return ConnectionConfig(
        MAIL_USERNAME=settings["MAIL_USERNAME"],
        MAIL_PASSWORD=settings["MAIL_PASSWORD"],
        MAIL_FROM=settings["MAIL_FROM"],
        MAIL_PORT=port,
        MAIL_SERVER=settings["MAIL_SERVER"],
        MAIL_FROM_NAME=settings["MAIL_FROM_NAME"],
        MAIL_STARTTLS=port != 465,
        MAIL_SSL_TLS=port == 465,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


async def send_waitlist_confirmation_email(
    recipient_email: str,
    student_name: str,
    activity_title: str,
    queue_position: int,
    team_name: str | None = None,
) -> bool:
    config = build_mail_config()
    if config is None:
        return False

    team_line = f"<p><strong>ทีม:</strong> {team_name}</p>" if team_name else ""
    message = MessageSchema(
        subject=f"ยืนยันการเข้าคิวสำรอง - {activity_title}",
        recipients=[recipient_email],
        body=(
            "<div style='font-family: Arial, sans-serif; line-height: 1.6;'>"
            f"<h2>ยืนยันการเข้าคิวสำรอง</h2>"
            f"<p>สวัสดี {student_name}</p>"
            f"<p>คุณถูกเพิ่มเข้ารายชื่อสำรองคิวของกิจกรรม <strong>{activity_title}</strong> เรียบร้อยแล้ว</p>"
            f"<p><strong>ลำดับคิวปัจจุบัน:</strong> {queue_position}</p>"
            f"{team_line}"
            "<p>หากมีที่นั่งว่าง ผู้ดูแลระบบสามารถตรวจสอบและเลื่อนคิวให้ตามลำดับได้</p>"
            "<p>อีเมลฉบับนี้เป็นการยืนยันว่าระบบได้รับข้อมูลการเข้าคิวของคุณแล้ว</p>"
            "</div>"
        ),
        subtype=MessageType.html,
    )

    try:
        await FastMail(config).send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send waitlist confirmation email")
        return False


async def send_waitlist_promoted_email(
    recipient_email: str,
    student_name: str,
    activity_title: str,
    team_name: str | None = None,
) -> bool:
    config = build_mail_config()
    if config is None:
        return False

    team_line = f"<p><strong>ทีม:</strong> {team_name}</p>" if team_name else ""
    message = MessageSchema(
        subject=f"คุณได้รับสิทธิ์เข้าร่วมกิจกรรมแล้ว - {activity_title}",
        recipients=[recipient_email],
        body=(
            "<div style='font-family: Arial, sans-serif; line-height: 1.6;'>"
            f"<h2>ยืนยันสิทธิ์เข้าร่วมกิจกรรม</h2>"
            f"<p>สวัสดี {student_name}</p>"
            f"<p>มีที่นั่งว่างในกิจกรรม <strong>{activity_title}</strong> แล้ว และระบบได้เลื่อนคุณจากคิวสำรองเป็นผู้ลงทะเบียนเรียบร้อยแล้ว</p>"
            f"{team_line}"
            "<p>กรุณาตรวจสอบข้อมูลการลงทะเบียนของคุณในระบบอีกครั้ง</p>"
            "<p>อีเมลฉบับนี้เป็นการแจ้งว่าคุณได้รับที่นั่งแล้ว</p>"
            "</div>"
        ),
        subtype=MessageType.html,
    )

    try:
        await FastMail(config).send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send waitlist promotion email")
        return False
