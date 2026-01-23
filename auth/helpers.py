"""
auth.helpers
~~~~~~~~~~~~

Fonctions helpers pour l'authentification API (endpoints de test).
"""

import os
from flask import request


# AUTHENTIFICATION API (TEST ENDPOINTS)

def testapi_authorized(req: request) -> bool:
    """
    Autorise les endpoints de test via X-API-Key.
    
    Les endpoints /api/test/* nécessitent une clé API pour l'accès CORS
    depuis des outils externes (ex: test-validation.html).
    
    Args:
        req: Objet Flask request
    
    Returns:
        True si la clé API est valide, False sinon
    """
    expected = os.environ.get("TEST_API_KEY")
    if not expected:
        return False
    return req.headers.get("X-API-Key") == expected


def api_key_required(func):
    """
    Décorateur pour protéger les endpoints API avec authentification par clé API.
    
    Usage:
        @app.route('/api/test/endpoint')
        @api_key_required
        def my_endpoint():
            ...
    
    Args:
        func: Fonction à décorer
    
    Returns:
        Wrapper qui vérifie l'authentification
    """
    from functools import wraps
    from flask import jsonify
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not testapi_authorized(request):
            return jsonify({"error": "Unauthorized. Valid X-API-Key required."}), 401
        return func(*args, **kwargs)
    
    return wrapper
