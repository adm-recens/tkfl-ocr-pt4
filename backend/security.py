def add_security_headers(app):
    """Adds security headers to all responses."""
    
    @app.after_request
    def set_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # HSTS (Strict-Transport-Security) - Enable only if using HTTPS
        # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
