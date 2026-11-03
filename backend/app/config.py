import os
from dotenv import load_dotenv

load_dotenv()


def _build_db_uri():
    """
    Supports two ways of configuring the database, so this works equally well
    against a local MySQL install or a hosted/managed MySQL (PlanetScale,
    Railway, AWS RDS, Clever Cloud, etc.):

    1. DATABASE_URL — a single ready-made connection string, exactly as most
       hosted MySQL providers hand it to you, e.g.:
       mysql+pymysql://user:password@host:3306/dbname
       (If the host gives you a bare "mysql://..." URL, change the scheme to
       "mysql+pymysql://" — SQLAlchemy needs the driver name in there.)

    2. DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD — separate fields,
       assembled into the URI for you. Used only if DATABASE_URL isn't set.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "shelfwise")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"


def _build_engine_options():
    """
    Many hosted MySQL providers require SSL and will refuse plain
    connections. Set DB_SSL=true in .env to enable it (no CA file needed
    for most providers' default certs); set DB_SSL_CA to a CA file path if
    your provider gives you one to pin.
    """
    options = {"pool_pre_ping": True}  # reconnects dead connections automatically
    if os.getenv("DB_SSL", "false").lower() in ("1", "true", "yes"):
        ssl_args = {}
        ca_path = os.getenv("DB_SSL_CA", "").strip()
        if ca_path:
            ssl_args["ca"] = ca_path
        options["connect_args"] = {"ssl": ssl_args}
    return options


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # kept for reference/scripts that want the individual pieces (seed.py)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "shelfwise")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SSL = os.getenv("DB_SSL", "false").lower() in ("1", "true", "yes")
    DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_ENGINE_OPTIONS = _build_engine_options()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google Gemini (get a key at https://aistudio.google.com/apikey).
    # "gemini-flash-latest" always points at Google's current Flash model, so it
    # keeps working as models are retired. Pin a specific model here if you prefer.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    # Tried automatically if the main model is overloaded (503) or rate limited (429).
    # Set to an empty value to disable the fallback.
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-lite-latest")

    # --- Invites / email (all optional) -------------------------------------
    # Where invite links should point (the URL your frontend is served from).
    # Leave blank in local dev: the app falls back to the browser's Origin.
    FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    INVITE_EXPIRY_DAYS = int(os.getenv("INVITE_EXPIRY_DAYS", "7") or 7)
    # SMTP is only needed if you want the server to email invites itself.
    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
    SMTP_USER = os.getenv("SMTP_USER", "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USER", "").strip()

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
