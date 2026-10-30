import os
from flask import Flask
from config import Config
from app.models import db

def create_app(config_class=Config):
    """Application factory for AutoVault."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance and upload directories exist
    try:
        if 'UPLOAD_FOLDER' in app.config and app.config['UPLOAD_FOLDER']:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)

        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///') and ':memory:' not in db_uri:
            db_path = db_uri.replace('sqlite:///', '')
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)

    # Apply ProxyFix for correct HTTPS / proxy headers handling on platforms like Vercel
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    except Exception:
        pass

    # Context processor to make current user helper available across all Jinja templates
    from app.routes.auth import get_current_user
    @app.context_processor
    def inject_user():
        return dict(current_user=get_current_user())

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.vehicle import vehicle_bp
    from app.routes.fuel import fuel_bp
    from app.routes.maintenance import maintenance_bp
    from app.routes.reminders import reminders_bp
    from app.routes.documents import documents_bp
    from app.routes.analytics import analytics_bp
    from app.routes.modules import modules_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(vehicle_bp)
    app.register_blueprint(fuel_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(modules_bp)

    # Initialize database tables and auto-seed demo data if empty
    with app.app_context():
        try:
            from app.models.user import User
            from app.models.vehicle import Vehicle
            from app.models.fuel import FuelEntry
            from app.models.maintenance import MaintenanceRecord
            from app.models.reminder import Reminder
            from app.models.document import Document
            db.create_all()

            if not app.config.get('TESTING') and User.query.first() is None:
                from seed import seed_demo_data_in_context
                seed_demo_data_in_context()
        except Exception as e:
            app.logger.warning(f"Database initialization deferred or failed: {e}")

    return app
