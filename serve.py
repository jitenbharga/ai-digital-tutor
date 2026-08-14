import os
import sys
import types

_root_dir = os.path.dirname(os.path.abspath(__file__))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

user_dir = os.path.join(_root_dir, "user")
if os.path.exists(user_dir) and user_dir not in sys.path:
    sys.path.insert(0, user_dir)

if "user" not in sys.modules or not hasattr(sys.modules["user"], "__path__"):
    user_mod = types.ModuleType("user")
    user_mod.__path__ = [user_dir]
    sys.modules["user"] = user_mod

from user.serve import app
