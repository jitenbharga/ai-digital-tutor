import os
import sys

_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

user_dir = os.path.join(_root_dir, "user")
if os.path.exists(user_dir) and user_dir not in sys.path:
    sys.path.insert(0, user_dir)

from user.serve import app
