"""Flask web layer. Routes call the same services as the console application."""
import os

from flask import Flask

from app.config import load_db_config
from app.db.connection import Database
from app.services.container import Services
from app.web.helpers import register_filters
from app.web.routes import bp


def create_app(services: Services = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("RPMS_SECRET_KEY", "dev-only-change-me")
    app.extensions["rpms"] = services or Services(Database(load_db_config()))
    app.register_blueprint(bp)
    register_filters(app)
    return app
