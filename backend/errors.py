from flask import jsonify, render_template, request

def register_error_handlers(app):
    """Registers global error handlers."""

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found"}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Server Error: {e}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal Server Error"}), 500
        return render_template('500.html'), 500

    @app.errorhandler(413)
    def request_entity_too_large(e):
        app.logger.warning(f"Request too large: {e}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "File too large"}), 413
        return render_template('500.html', error_message="File too large"), 413
