import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _is_serverless():
    """Detect if running in Vercel/Lambda or read-only serverless environment."""
    if any(os.environ.get(k) for k in ('VERCEL', 'VERCEL_ENV', 'VERCEL_REGION', 'AWS_LAMBDA_FUNCTION_NAME', 'LAMBDA_TASK_ROOT')):
        return True
    if os.path.exists('/var/task'):
        return True
    instance_dir = os.path.join(BASE_DIR, 'instance')
    try:
        os.makedirs(instance_dir, exist_ok=True)
        test_file = os.path.join(instance_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('1')
        os.remove(test_file)
        return False
    except (OSError, IOError, PermissionError):
        return True

def _get_database_uri():
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        return db_url.replace('postgres://', 'postgresql://', 1)
    if db_url:
        return db_url
    if _is_serverless():
        return 'sqlite:////tmp/autovault.db'
    return f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'autovault.db')}"

def _get_upload_folder():
    if _is_serverless():
        return '/tmp/uploads'
    return os.path.join(BASE_DIR, 'instance', 'uploads')

class Config:
    """Application configuration for AutoVault."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'autovault-dev-secret-key-3rd-sem-cybersec-2026'
    IS_VERCEL = _is_serverless()
    SQLALCHEMY_DATABASE_URI = _get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    UPLOAD_FOLDER = _get_upload_folder()

    # Session cookie hardening & cross-environment persistence
    SESSION_COOKIE_NAME = 'autovault_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true' or (
        _is_serverless() and os.environ.get('SESSION_COOKIE_SECURE', '').lower() != 'false'
    )
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)


