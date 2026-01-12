import os
from flask import Flask
from backend.config import config
from backend.db import init_app as init_db_pool

def create_app(config_name='default'):
    # Determine template and static folders relative to this file
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # Load configuration
    # If config_name is passed as env var, use it, otherwise default
    if os.environ.get('FLASK_CONFIG'):
        config_name = os.environ.get('FLASK_CONFIG')
        
    app.config.from_object(config[config_name])
    
    # Initialize Database Pool
    init_db_pool(app)

    # Configure Logging
    from backend.logger import configure_logging
    configure_logging(app)

    # Register Error Handlers
    from backend.errors import register_error_handlers
    register_error_handlers(app)

    # Enable CSRF Protection
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Add Security Headers
    from backend.security import add_security_headers
    add_security_headers(app)

    # Register Blueprints
    from backend.routes.main import main_bp
    from backend.routes.api import api_bp
    from backend.routes.api_beta import api_beta_bp
    from backend.routes.api_beta_v2 import api_beta_v2_bp
    from backend.routes.main_beta_v2 import main_beta_v2_bp
    from backend.routes.comparison import comparison_bp
    from backend.routes.api_bulk import api_bulk_bp
    from backend.routes.api_queue import api_queue_bp  # Import the queue API blueprint

    # Exempt queue API from CSRF protection (it doesn't use forms)
    csrf.exempt(api_queue_bp)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(api_beta_bp, url_prefix='/api')
    app.register_blueprint(api_beta_v2_bp)  # Already has /api/beta_v2 prefix
    app.register_blueprint(main_beta_v2_bp)  # Already has /beta_v2 prefix
    app.register_blueprint(comparison_bp)  # Has /api/comparison prefix
    app.register_blueprint(api_bulk_bp, url_prefix='/api/bulk')  # Bulk upload API
    app.register_blueprint(api_queue_bp, url_prefix='/api/queue')  # Queue workflow API

    return app
