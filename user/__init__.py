import sys
import os
import types

_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)

if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

if "user" not in sys.modules or not hasattr(sys.modules["user"], "__path__"):
    user_mod = types.ModuleType("user")
    user_mod.__path__ = [_current_dir]
    user_mod.__file__ = os.path.join(_current_dir, "__init__.py")
    sys.modules["user"] = user_mod
