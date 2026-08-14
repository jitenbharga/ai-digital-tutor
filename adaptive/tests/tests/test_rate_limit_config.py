"""
SEC H-4: rate limiting must use a shared store in production so limits hold
across uvicorn workers and replicas. The app should fail closed if a production
deployment is missing RATE_LIMIT_STORAGE_URI.

We test the pure ``validate_rate_limit_config`` function directly.
"""
import pytest

from rate_limit import validate_rate_limit_config


def test_production_without_store_fails_closed():
    with pytest.raises(RuntimeError):
        validate_rate_limit_config("production", None)
    with pytest.raises(RuntimeError):
        validate_rate_limit_config("PRODUCTION", "")  # case-insensitive, empty


def test_production_with_redis_uri_ok():
    validate_rate_limit_config("production", "redis://redis:6379")


def test_dev_and_test_allow_in_memory():
    # Single-process dev/test may use the in-memory store without weakening.
    validate_rate_limit_config("development", None)
    validate_rate_limit_config("test", None)
    validate_rate_limit_config("staging", None)  # only production is hard-required
