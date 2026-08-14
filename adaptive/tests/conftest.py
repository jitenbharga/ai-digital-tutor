"""
conftest.py — sets up all stubs BEFORE pytest collects test modules.
This runs before any test file is imported.
"""
import sys
import os
import types
from unittest.mock import MagicMock

# ─── Project root on path ───
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ─── Env vars needed by database.py ───
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt-0123456789abcdef")
os.environ.setdefault("MISTRAL_API_KEY_1", "test-dummy-key")
os.environ.setdefault("GROQ_API_KEY_1", "test-dummy-key")
os.environ.setdefault("ENVIRONMENT", "test")

# ═══════════════════════════════════════════
# TORCH STUBS
# ═══════════════════════════════════════════
# Prefer REAL torch when installed — tests like test_checkpoint.py need it.
# Only fall back to the lightweight stub when torch can't be imported.
try:
    import torch as _real_torch  # noqa: F401
    TORCH_IS_STUB = False
except Exception:
    TORCH_IS_STUB = True

if TORCH_IS_STUB and "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")
    torch_stub.__stub__ = True  # flag so tests can skip when torch is faked
    torch_stub.float32 = "float32"
    torch_stub.no_grad = lambda: type("ctx", (), {
        "__enter__": lambda s: None, "__exit__": lambda s,*a: None
    })()
    torch_stub.device = MagicMock
    # utils/device.py imports call torch.cuda.is_available() at import time —
    # provide a harmless namespace so the whole suite can import cleanly.
    torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch_stub.tensor = lambda data, **kw: MagicMock(
        item=lambda: 0,
        tolist=lambda: data if isinstance(data, list) else [data]
    )
    torch_stub.argmax = lambda t, **kw: MagicMock(item=lambda: 0)
    torch_stub.save = MagicMock()
    torch_stub.load = MagicMock(return_value={
        "model": {}, "target_model": {}, "optimizer": {},
        "epsilon": 0.5, "step_counter": 100
    })
    torch_stub.Tensor = MagicMock
    sys.modules["torch"] = torch_stub

    nn_stub = types.ModuleType("torch.nn")

    class _StubModule:
        # Minimal nn.Module surface so DQN/DKT can be *constructed* under the stub
        # (real torch in CI provides the real thing). Enough for read paths /
        # session lookups that build the tutor but don't run a forward pass.
        def __init__(self, *a, **k):
            pass

        def to(self, *a, **k):
            return self

        def eval(self, *a, **k):
            return self

        def train(self, *a, **k):
            return self

        def parameters(self, *a, **k):
            return iter(())

        def named_parameters(self, *a, **k):
            return iter(())

        def state_dict(self, *a, **k):
            return {}

        def load_state_dict(self, *a, **k):
            return None

        def modules(self, *a, **k):
            return iter(())

        def children(self, *a, **k):
            return iter(())

        def __call__(self, *a, **k):
            return None

    nn_stub.Module = _StubModule
    nn_stub.Sequential = MagicMock()
    nn_stub.Linear = MagicMock()
    nn_stub.ReLU = MagicMock()
    nn_stub.MSELoss = MagicMock()
    nn_stub.utils = MagicMock()
    sys.modules["torch.nn"] = nn_stub

    optim_stub = types.ModuleType("torch.optim")
    optim_stub.Adam = MagicMock()
    sys.modules["torch.optim"] = optim_stub

# ═══════════════════════════════════════════
# MOTOR / DOTENV STUBS
# ═══════════════════════════════════════════
# W2: integration tests (INTEGRATION_TESTS=1) use REAL motor so they can talk to
# a live MongoDB (CI service container) or mongomock_motor (local). Unit tests
# keep the lightweight MagicMock stub. Default behaviour is unchanged.
_INTEGRATION = os.getenv("INTEGRATION_TESTS") == "1"
if not _INTEGRATION and "motor" not in sys.modules:
    motor_stub = types.ModuleType("motor")
    motor_aio = types.ModuleType("motor.motor_asyncio")
    motor_aio.AsyncIOMotorClient = MagicMock()
    sys.modules["motor"] = motor_stub
    sys.modules["motor.motor_asyncio"] = motor_aio

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_stub

# ═══════════════════════════════════════════
# LANGCHAIN STUBS
# ═══════════════════════════════════════════
_BaseChatModel = type("BaseChatModel", (), {})

if "langchain_core" not in sys.modules:
    lc_core = types.ModuleType("langchain_core")
    sys.modules["langchain_core"] = lc_core

    lc_msgs = types.ModuleType("langchain_core.messages")
    lc_msgs.HumanMessage = type("HumanMessage", (), {
        "__init__": lambda s, content="": setattr(s, "content", content)
    })
    sys.modules["langchain_core.messages"] = lc_msgs

    lc_models = types.ModuleType("langchain_core.language_models")
    lc_models.BaseChatModel = _BaseChatModel
    sys.modules["langchain_core.language_models"] = lc_models

    lc_chat = types.ModuleType("langchain_core.language_models.chat_models")
    lc_chat.BaseChatModel = _BaseChatModel
    sys.modules["langchain_core.language_models.chat_models"] = lc_chat

# langchain provider stubs
for mod_name in [
    "langchain_mistralai", "langchain_mistralai.chat_models",
    "langchain_groq", "langchain_google_genai",
    "langchain_huggingface", "langchain_huggingface.chat_models",
]:
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        m.ChatMistralAI = MagicMock()
        m.ChatGroq = MagicMock()
        m.ChatGoogleGenerativeAI = MagicMock()
        m.ChatHuggingFace = MagicMock()
        m.HuggingFaceEndpoint = MagicMock()
        sys.modules[mod_name] = m

# ═══════════════════════════════════════════
# PYDANTIC STUB (BaseModel needs to work)
# ═══════════════════════════════════════════
# pydantic is actually installed, so no stub needed

# ═══════════════════════════════════════════
# SLOWAPI STUBS
# ═══════════════════════════════════════════
# Prefer REAL slowapi when installed. Its limiter decorator uses functools.wraps,
# so rate-limited endpoints keep their real FastAPI signature + dependency tree.
# The MagicMock stub replaces decorated endpoints with a mock, erasing their
# guards — which makes tests/test_route_auth_contract.py (route-guard
# introspection) see a false "unguarded" result. Fall back to the lightweight
# stub only when slowapi genuinely can't be imported.
try:
    import slowapi as _real_slowapi  # noqa: F401
    SLOWAPI_IS_STUB = False
except Exception:
    SLOWAPI_IS_STUB = True

if SLOWAPI_IS_STUB:
    for mod_name in ["slowapi", "slowapi.errors", "slowapi.middleware", "slowapi.util"]:
        if mod_name not in sys.modules:
            m = types.ModuleType(mod_name)
            m.Limiter = MagicMock()
            m.RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})
            m.SlowAPIMiddleware = MagicMock()
            m._rate_limit_exceeded_handler = MagicMock()
            m.get_remote_address = MagicMock()
            sys.modules[mod_name] = m
