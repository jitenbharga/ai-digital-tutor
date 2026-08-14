#!/usr/bin/env python3
"""Re-serialize legacy PyTorch checkpoints into a ``weights_only=True``-safe form.

Context (BUG-1 / SEC-1)
-----------------------
The application now loads every checkpoint with ``torch.load(..., weights_only=True)``
so a tampered checkpoint cannot execute arbitrary code via pickle. A checkpoint
that was saved with non-tensor / custom-class payloads may fail to load under the
restricted unpickler. This one-shot, *manually run* utility loads such a checkpoint
under a full (trusted) unpickle and re-saves it containing only load-safe types:
torch tensors and plain ``dict/list/tuple/str/int/float/bool`` values. It optionally
emits a ``.safetensors`` copy of the model ``state_dict`` (preferred, per the audit).

This script is deliberately NOT imported by the app and lives outside the modules
scanned by the B614 gate (``bandit -r serve.py core api models``). Run it only on
checkpoints you trust (i.e. produced by our own training jobs).

Usage
-----
    python scripts/reserialize_checkpoints.py checkpoints/dqn_model.pt
    python scripts/reserialize_checkpoints.py checkpoints/*.pt --safetensors
    python scripts/reserialize_checkpoints.py checkpoints/dkt_model.pt --out /tmp/dkt_safe.pt

By default the file is rewritten in place after a ``.bak`` backup is created.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from typing import Any

import torch

_SAFE_SCALARS = (str, int, float, bool, bytes, type(None))


def _is_load_safe(obj: Any) -> bool:
    """True if ``obj`` is composed solely of tensors + plain containers/scalars,
    i.e. it will round-trip through ``torch.load(..., weights_only=True)``."""
    if isinstance(obj, torch.Tensor) or isinstance(obj, _SAFE_SCALARS):
        return True
    if isinstance(obj, dict):
        return all(
            isinstance(k, _SAFE_SCALARS) and _is_load_safe(v) for k, v in obj.items()
        )
    if isinstance(obj, (list, tuple, set)):
        return all(_is_load_safe(v) for v in obj)
    return False


def _sanitize(obj: Any) -> Any:
    """Best-effort conversion of common unsafe leaves (e.g. numpy arrays) into
    load-safe equivalents. Raises if an item cannot be made safe."""
    if isinstance(obj, torch.Tensor) or isinstance(obj, _SAFE_SCALARS):
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_sanitize(v) for v in obj)
    # numpy scalar/array -> torch tensor (import lazily; numpy may be absent)
    try:
        import numpy as np  # noqa: WPS433 (local import is intentional here)

        if isinstance(obj, np.ndarray):
            return torch.from_numpy(obj)
        if isinstance(obj, np.generic):
            return obj.item()
    except ImportError:  # pragma: no cover - numpy nearly always present
        pass
    raise TypeError(
        f"Cannot make value of type {type(obj)!r} load-safe; inspect this "
        f"checkpoint manually before re-serializing."
    )


def reserialize(path: str, out: str | None, emit_safetensors: bool) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    # Trusted, one-time full load. nosec: this utility is run manually on our own
    # checkpoints, is not imported by the app, and is outside the B614 scan scope.
    saved = torch.load(path, map_location="cpu", weights_only=False)  # nosec B614

    safe = _sanitize(saved)
    if not _is_load_safe(safe):
        raise RuntimeError(
            f"{path}: still not load-safe after sanitize; aborting to avoid a "
            f"silently broken checkpoint."
        )

    target = out or path
    if target == path:
        backup = path + ".bak"
        shutil.copy2(path, backup)
        print(f"  backed up original -> {backup}")

    torch.save(safe, target)
    # Verify the re-saved file actually loads under the restricted unpickler.
    torch.load(target, map_location="cpu", weights_only=True)
    print(f"  re-serialized (weights_only-safe) -> {target}")

    if emit_safetensors:
        _emit_safetensors(safe, target)


def _emit_safetensors(safe: Any, target: str) -> None:
    try:
        from safetensors.torch import save_file
    except ImportError:
        print("  [skip] safetensors not installed (pip install safetensors)")
        return

    # Prefer an explicit model state_dict if present; else any flat tensor dict.
    state = None
    if isinstance(safe, dict):
        for key in ("model", "model_state", "state_dict"):
            if key in safe and isinstance(safe[key], dict):
                state = safe[key]
                break
        if state is None and all(isinstance(v, torch.Tensor) for v in safe.values()):
            state = safe
    if state is None:
        print("  [skip] no flat tensor state_dict found for safetensors export")
        return

    st_path = os.path.splitext(target)[0] + ".safetensors"
    save_file({k: v.contiguous() for k, v in state.items()}, st_path)
    print(f"  wrote safetensors -> {st_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="checkpoint file(s) to re-serialize")
    parser.add_argument("--out", default=None, help="write to this path instead of in place (single input only)")
    parser.add_argument("--safetensors", action="store_true", help="also emit a .safetensors copy of the state_dict")
    args = parser.parse_args(argv)

    if args.out and len(args.paths) != 1:
        parser.error("--out can only be used with a single input path")

    failures = 0
    for path in args.paths:
        print(f"[reserialize] {path}")
        try:
            reserialize(path, args.out, args.safetensors)
        except Exception as exc:  # noqa: BLE001 - CLI: report and continue
            failures += 1
            print(f"  ERROR: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
