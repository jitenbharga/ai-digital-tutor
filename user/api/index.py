import os
import sys

_user_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _user_dir not in sys.path:
    sys.path.insert(0, _user_dir)

from serve import app

handler = app
