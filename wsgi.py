import os
import sys

# Ensure the project directory is in the Python path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app, init_db

# Initialize database on startup
init_db()

# Gunicorn entry point
application = app
