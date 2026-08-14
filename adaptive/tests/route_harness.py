"""
Shared route-test harness (not collected by pytest — no `test_` prefix).

Provides:
  * wire_mongomock(mockdb) — point every module's collection handle (and the
    lazy `database.db`) at an in-memory async Mongo.
  * install_fake_llm()     — replace core.llm_utils.call_llm / call_llm_text
    (and every module that imported them) with deterministic canned responses,
    so LLM-backed routes execute without a provider.
  * run_async(coro)        — drive a coroutine for seeding.
"""
import asyncio
import re as _re
import sys


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def wire_mongomock(mockdb):
    """Point module-level collection handles AND the lazy database.db at mockdb."""
    import database
    database.db = mockdb  # retention_tracker / reminder_engine use db["..."] lazily
    patched = 0
    for module in list(sys.modules.values()):
        ns = getattr(module, "__dict__", None)
        if not ns:
            continue
        name = getattr(module, "__name__", "")
        is_app = name.startswith(("core.", "api.")) or name == "serve"
        for attr in list(ns.keys()):
            if attr.startswith("_"):
                # PRIVATE lazy-cached handle (retention_tracker._collection,
                # reminder_engine._prefs_col): reset so it re-binds to the freshly
                # wired database.db on next use. Without this a handle cached in an
                # earlier test leaks across test modules and breaks (MagicMock db).
                if is_app and _re.fullmatch(r"_[a-z_]*col(lection)?", attr):
                    try:
                        setattr(module, attr, None)
                    except Exception:
                        pass
            elif attr.endswith("_collection") or attr == "students_col":
                try:
                    setattr(module, attr, mockdb[attr])
                    patched += 1
                except Exception:
                    pass
    return patched


# A deterministic question shape covering the fields the quiz/question routes read.
def _question(i=0):
    return {
        "question": f"What is {i}+{i}?",
        "options": [str(i), str(i + i), str(i + 1), str(i + 2)],
        "answer": str(i + i),
        "correct_answer": str(i + i),
        "correct_option": 1,
        "concept": "arithmetic",
        "topic": "arithmetic",
        "difficulty": 0.5,
        "explanation": "Add the two numbers.",
        "hint": "Combine the terms.",
        "type": "mcq",
    }


def _nodes():
    # Shape expected by core/curriculum_engine._generate_tree_llm.
    return [
        {"node_id": "n1", "title": "Basics", "level": 1, "parent_id": None,
         "prerequisites": [], "order": 1, "node_type": "topic", "concept_aliases": ["basics"]},
        {"node_id": "n2", "title": "Intermediate", "level": 2, "parent_id": "n1",
         "prerequisites": ["n1"], "order": 2, "node_type": "topic", "concept_aliases": ["intermediate"]},
    ]


def _value_for(required_key):
    if required_key in ("questions",):
        return [_question(i) for i in (2, 3, 4)]
    if required_key in ("question",):
        return _question(2)
    if required_key == "nodes":
        return _nodes()
    if required_key in ("steps", "milestones", "examples", "prerequisites"):
        return ["Step one.", "Step two."]
    return "Canned deterministic response for testing."


async def _fake_call_llm(models, prompt=None, required_key=None, schema=None, *a, **k):
    # Kitchen-sink dict: has required_key plus common fields routes read via [] / .get().
    data = {
        "model_used": "fake", "_cached": False,
        "explanation": "Canned explanation.", "concept": "arithmetic",
        "core_concept": "Canned core concept.", "difficulty": 0.5,
        "guiding_question": "What is the next step?", "concept_hint": "Recall the rule.",
        "hint": "Try isolating the variable.", "answer": "4", "correct_answer": "4",
        "feedback": "Looks reasonable overall.", "summary": "Canned summary.",
        "title": "Canned Title", "description": "Canned description.",
        "steps": ["Step one.", "Step two."], "examples": ["Example one."],
        "questions": [_question(i) for i in (2, 3, 4)],
        "question": _question(2), "nodes": _nodes(), "edges": [],
        "is_correct": True, "score": 0.8, "verified": True,
    }
    if required_key:
        data[required_key] = _value_for(required_key)
    return data


async def _fake_call_llm_text(models, prompt=None, min_length=10, *a, **k):
    return "This is a deterministic canned explanation produced for testing purposes."


import json as _json


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeChat:
    """Stand-in for a LangChain chat model (incl. vision). ainvoke returns JSON
    content that parse_json_robust can read; used by solution-check/step-check."""

    def __init__(self, *a, **k):
        pass

    async def ainvoke(self, *a, **k):
        return _FakeResp(_json.dumps({
            "has_error": True, "transcription": "x + 2 = 4",
            "first_error_step": "step 2", "why_wrong": "sign flip",
            "answer": "2", "is_correct": True, "feedback": "Looks close.",
            "score": 0.8, "explanation": "Canned explanation.",
            "questions": [_question(2)], "nodes": _nodes(),
        }))

    def invoke(self, *a, **k):
        return _FakeResp("{}")


_PROVIDER_CLASSES = {
    "langchain_google_genai": ["ChatGoogleGenerativeAI"],
    "langchain_mistralai": ["ChatMistralAI"],
    "langchain_mistralai.chat_models": ["ChatMistralAI"],
    "langchain_groq": ["ChatGroq"],
    "langchain_huggingface": ["ChatHuggingFace", "HuggingFaceEndpoint"],
    "langchain_huggingface.chat_models": ["ChatHuggingFace"],
}


def install_fake_llm():
    """Replace call_llm / call_llm_text everywhere they are bound."""
    import core.llm_utils as U
    U.call_llm = _fake_call_llm
    U.call_llm_text = _fake_call_llm_text
    for module in list(sys.modules.values()):
        ns = getattr(module, "__dict__", None)
        if not ns:
            continue
        if callable(ns.get("call_llm")):
            ns["call_llm"] = _fake_call_llm
        if callable(ns.get("call_llm_text")):
            ns["call_llm_text"] = _fake_call_llm_text
    # Vision / direct-provider seams (solution-check, step-check build a
    # ChatGoogleGenerativeAI inline and call .ainvoke): swap the provider classes.
    for mod_name, classes in _PROVIDER_CLASSES.items():
        mod = sys.modules.get(mod_name)
        if mod:
            for cls in classes:
                if hasattr(mod, cls):
                    setattr(mod, cls, _FakeChat)
