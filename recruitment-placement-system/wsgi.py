"""WSGI entry point used by PythonAnywhere (and any WSGI server).

Local Windows test:  python -m waitress --host=127.0.0.1 --port=8000 wsgi:app
"""
from app.utils.logger import setup_logging
from app.web import create_app

setup_logging()
app = create_app()
