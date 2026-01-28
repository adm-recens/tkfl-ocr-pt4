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
    from backend.routes.api_queue import api_queue_bp
    from backend.routes.api_training import api_training_bp
    from backend.routes.learning import learning_bp

    # Exempt queue API from CSRF protection (it doesn't use forms)
    csrf.exempt(api_queue_bp)
    csrf.exempt(api_training_bp) # Also exempt training API
    csrf.exempt(learning_bp)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(api_queue_bp, url_prefix='/api/queue')
    app.register_blueprint(api_training_bp, url_prefix='/api/training')
    app.register_blueprint(learning_bp)

    return app
