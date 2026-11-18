"""Start the Recruitment & Placement Management System console application.

    python main.py
Connection settings are read from environment variables (see README.md).
"""
from app.cli.menus import run

if __name__ == "__main__":
    run()
