"""Passenger WSGI entry point for shared hosting (A2 Hosting / cPanel).

Passenger expects a WSGI `application` object. FastAPI is ASGI, so we use
the `a2wsgi` adapter to bridge them. WebSockets won't work through Passenger,
but the REST API and replay features work fine.
"""

import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, project_root)

from a2wsgi import ASGIMiddleware
from server.api.app import create_app

# Create the FastAPI app
asgi_app = create_app()

# Wrap it for WSGI (Passenger compatibility)
application = ASGIMiddleware(asgi_app)
