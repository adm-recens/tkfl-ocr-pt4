import logging
from logging.handlers import RotatingFileHandler
import os

def configure_logging(app):
    """Configures logging for the application."""
    
    # Remove default handlers
    del app.logger.handlers[:]
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set log level based on config
    log_level = logging.DEBUG if app.debug else logging.INFO
    app.logger.setLevel(log_level)
    
    # Formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'), 
        maxBytes=10 * 1024 * 1024, # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Add handlers
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    
    app.logger.info("Logging configured.")

    # Configure separate ML logger
    ml_logger = logging.getLogger('ml')
    # Prevent propagation to root handlers (so ML logs don't duplicate)
    ml_logger.propagate = False
    ml_logger.setLevel(log_level)

    ml_file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'ml.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    ml_file_handler.setFormatter(formatter)
    ml_file_handler.setLevel(log_level)

    # Optionally add console handler for ML as well
    ml_console = logging.StreamHandler()
    ml_console.setFormatter(formatter)
    ml_console.setLevel(log_level)

    ml_logger.addHandler(ml_file_handler)
    ml_logger.addHandler(ml_console)

    app.logger.info("ML logger configured (logs/ml.log)")
