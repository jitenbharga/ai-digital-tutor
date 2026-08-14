"""
Security regression tests for the July 2026 hardening pass.

Covers the pure, dependency-light logic behind the fixes so they can run in CI
without a live Mongo/LLM (see conftest.py stubs):

  * SEC-1  IDOR — require_self_or_guardian: A cannot read/write B's data
  * SEC-2  ReDoS — safe_topic_filter escapes user regex + caps length
  * SEC-4  Upload — magic-byte verification rejects mislabeled/binary files
  * SEC-4  Upload — safe basename strips path traversal

Integration tests for the 429 paths (rate-limit and daily budget) require a
running app + Mongo and are exercised via test_endpoints.py against a live
server; they are intentionally not duplicated here.
"""
import asyncio
import re
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _req(**path_params):
    return SimpleNamespace(path_params=path_params, query_params={})


# ── SEC-1: IDOR ───────────────────────────────────────────────────────────

def test_idor_self_allowed():
    from dependencies import require_self_or_guardian
    check = require_self_or_guardian("student_id")
    user = {"username": "alice", "role": "student"}
    assert _run(check(_req(student_id="alice"), user)) is user


def test_idor_other_student_forbidden():
    from fastapi import HTTPException
    from dependencies import require_self_or_guardian
    check = require_self_or_guardian("student_id")
    attacker = {"username": "attacker", "role": "student"}
    with pytest.raises(HTTPException) as ei:
        _run(check(_req(student_id="victim"), attacker))
    assert ei.value.status_code == 403


def test_idor_guardian_of_child_allowed():
    from dependencies import require_self_or_guardian
    check = require_self_or_guardian("student_id")
    guardian = {"username": "mom", "role": "guardian", "linked_children": ["kid"]}
    assert _run(check(_req(student_id="kid"), guardian)) is guardian


def test_idor_guardian_of_other_child_forbidden():
    from fastapi import HTTPException
    from dependencies import require_self_or_guardian
    check = require_self_or_guardian("student_id")
    guardian = {"username": "mom", "role": "guardian", "linked_children": ["kid"]}
    with pytest.raises(HTTPException) as ei:
        _run(check(_req(student_id="not_my_kid"), guardian))
    assert ei.value.status_code == 403


# ── SEC-2: regex injection / ReDoS ─────────────────────────────────────────

def test_safe_topic_filter_escapes_evil_regex():
    from utils.mongo_safe import safe_topic_filter
    evil = "(a+)+$"
    f = safe_topic_filter(evil)
    assert f["$regex"] == re.escape(evil)   # literal, not a live pattern
    assert f["$options"] == "i"


def test_safe_topic_filter_caps_length():
    from utils.mongo_safe import safe_topic_filter, MAX_TOPIC_LEN
    f = safe_topic_filter("x" * 5000)
    assert len(f["$regex"].replace("\\", "")) <= MAX_TOPIC_LEN


def test_exact_topic_value_normalizes():
    from utils.mongo_safe import exact_topic_value
    assert exact_topic_value("  Calculus  ") == "calculus"


# ── SEC-4: upload hardening ────────────────────────────────────────────────

def test_magic_bytes_pdf_ok():
    from core.user_materials import verify_magic_bytes
    verify_magic_bytes(b"%PDF-1.7\n...", "pdf")  # should not raise


def test_magic_bytes_fake_pdf_rejected():
    from core.user_materials import verify_magic_bytes
    with pytest.raises(ValueError):
        verify_magic_bytes(b"GIF89a not a pdf", "pdf")


def test_magic_bytes_binary_txt_rejected():
    from core.user_materials import verify_magic_bytes
    with pytest.raises(ValueError):
        verify_magic_bytes(bytes(range(256)) * 40, "txt")


def test_magic_bytes_real_text_ok():
    from core.user_materials import verify_magic_bytes
    verify_magic_bytes("hello world\nsome notes".encode(), "txt")  # no raise


def test_safe_basename_strips_traversal():
    from utils.upload import safe_basename as _safe_basename
    assert "/" not in _safe_basename("../../etc/passwd")
    assert "\\" not in _safe_basename("..\\..\\windows\\system32\\x.txt")
    assert _safe_basename("../../etc/passwd") == "passwd"
