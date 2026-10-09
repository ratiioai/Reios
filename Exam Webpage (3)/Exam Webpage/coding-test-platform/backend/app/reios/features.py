"""
Paid add-ons the super admin switches on per event organization: certificates, branding, email results.
Colleges never get them.
"""
import base64
import hashlib
import io
import re
import smtplib
from email.message import EmailMessage
from typing import Optional, Tuple

from fastapi import HTTPException, status

from app.config import settings
from app.reios.models import Attempt, College

FEATURES = {
    "branding": "Organization logo and colour on its students' screens",
    "email_results": "Email each student their result",
}
LOGO_MAX_BYTES = 300 * 1024
LOGO_RE = re.compile(r"^data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=]+)$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def has_feature(org: Optional[College], key: str) -> bool:
    return bool(org and org.org_type == "event" and key in (org.features or []))


def require_feature(org: Optional[College], key: str) -> None:
    if not has_feature(org, key):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"{FEATURES[key]} isn't included in this event's plan")


def clean_features(org_type: str, features) -> list:
    if org_type != "event":
        return []
    unknown = set(features or []) - set(FEATURES)
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown features: {sorted(unknown)}")
    return sorted(set(features or []))


def check_logo(logo: Optional[str]) -> Optional[str]:
    if not logo:
        return None
    m = LOGO_RE.match(logo.strip())
    if not m:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The logo must be a PNG or JPG image")
    if len(base64.b64decode(m.group(2))) > LOGO_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The logo must be smaller than 300 KB")
    return logo.strip()


def logo_image(org: College) -> Optional[Tuple[bytes, str]]:
    """The organization's logo as (bytes, mime type), decoded from the stored data URL."""
    m = LOGO_RE.match((org.logo or "").strip())
    if not m:
        return None
    return base64.b64decode(m.group(2)), "image/png" if m.group(1) == "png" else "image/jpeg"


def branding(org: Optional[College]) -> Optional[dict]:
    if not has_feature(org, "branding"):
        return None
    # A link to the logo, not the image itself: a logo can be ~300 KB and this goes out with every
    # sign-in and page load. The ?v= changes with the logo, so browsers can cache the link for a day.
    logo = None
    if org.logo:
        logo = f"/api/reios/auth/logo/{org.code}?v={hashlib.sha256(org.logo.encode()).hexdigest()[:12]}"
    return {"name": org.name, "logo": logo, "color": org.brand_color}


# ── Certificates ──────────────────────────────────────────────────────────

def certificate_id(attempt: Attempt) -> str:
    raw = f"{attempt.id}:{attempt.student_id}:{attempt.exam_id}:{settings.SECRET_KEY}"
    return f"R-{attempt.id}-{hashlib.sha256(raw.encode()).hexdigest()[:8].upper()}"


def _latin(text: str) -> str:
    # Built-in PDF fonts cover Latin-1 only
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def _rgb(hex_color: Optional[str]):
    c = hex_color if hex_color and COLOR_RE.match(hex_color) else "#4f46e5"
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def certificate_pdf(attempt: Attempt, percentage: float) -> bytes:
    from fpdf import FPDF

    org, exam, student = attempt.exam.college, attempt.exam, attempt.student
    color = _rgb(org.brand_color if has_feature(org, "branding") else None)
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    w, h = 297, 210
    pdf.set_draw_color(*color)
    pdf.set_line_width(2.2)
    pdf.rect(10, 10, w - 20, h - 20)
    pdf.set_line_width(0.5)
    pdf.rect(15, 15, w - 30, h - 30)

    y = 28
    if has_feature(org, "branding") and org.logo:
        m = LOGO_RE.match(org.logo)
        if m:
            try:
                pdf.image(io.BytesIO(base64.b64decode(m.group(2))), x=(w - 30) / 2, y=y, h=22, keep_aspect_ratio=True)
                y += 26
            except Exception:
                pass

    def line(text, size, style="", gap=4, rgb=(30, 30, 40)):
        nonlocal y
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*rgb)
        pdf.set_xy(20, y)
        pdf.cell(w - 40, size * 0.45, _latin(text), align="C")
        y += size * 0.45 + gap

    line(org.name, 16, "B", 6, color)
    line("CERTIFICATE OF ACHIEVEMENT", 26, "B", 10)
    line("This certifies that", 13, "", 4, (90, 90, 100))
    line(student.name, 30, "B", 4, color)
    line(f"Roll number {student.roll_no}", 11, "", 8, (90, 90, 100))
    line("has successfully completed", 13, "", 4, (90, 90, 100))
    line(exam.title, 18, "B", 6)
    line(f"scoring {attempt.total_score:g} / {attempt.max_score:g}  ({percentage:g}%)", 14, "", 4)

    date = attempt.submitted_at.strftime("%d %B %Y") if attempt.submitted_at else ""
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110, 110, 120)
    pdf.set_xy(25, h - 32)
    pdf.cell(120, 5, _latin(f"Date: {date}"))
    pdf.set_xy(w - 145, h - 32)
    pdf.cell(120, 5, f"Certificate ID: {certificate_id(attempt)}", align="R")
    pdf.set_xy(20, h - 25)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(w - 40, 4, "Issued through Reios", align="C")
    return bytes(pdf.output())


# ── Email ─────────────────────────────────────────────────────────────────

def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send_emails(messages) -> tuple:
    """messages: [(to, subject, text)]. Returns (sent, failed: [(to, error)]). One connection for all."""
    if not smtp_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Email isn't set up on this server. Ask the Reios team to configure SMTP")
    sent, failed = 0, []
    try:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        if settings.SMTP_STARTTLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't connect to the email server: {exc}")
    with server:
        for to, subject, text in messages:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
            msg.set_content(text)
            try:
                server.send_message(msg)
                sent += 1
            except Exception as exc:
                failed.append((to, str(exc)[:200]))
    return sent, failed
