"""Start the web application at http://127.0.0.1:5000

    python run_web.py
"""
from app.utils.logger import setup_logging
from app.web import create_app

if __name__ == "__main__":
    setup_logging()
    create_app().run(debug=False, host="127.0.0.1", port=5000)
