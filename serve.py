import os
import sys

# Ensure backend and user directories are on sys.path
backend_path = os.path.join(os.path.dirname(__file__), "backend")
if os.path.exists(backend_path) and backend_path not in sys.path:
    sys.path.insert(0, backend_path)

user_path = os.path.join(os.path.dirname(__file__), "user")
if os.path.exists(user_path) and user_path not in sys.path:
    sys.path.insert(0, user_path)

from serve import app

# Export app for Vercel Serverless
