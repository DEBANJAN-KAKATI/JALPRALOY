"""Vercel Serverless Function entrypoint for JalProloy API."""
import os
import sys

# Add the backend directory to Python sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Ensure demo_mode is True or live_mode is enabled for serverless execution
os.environ.setdefault("DEMO_MODE", "true")

from app.main import app  # noqa: E402
