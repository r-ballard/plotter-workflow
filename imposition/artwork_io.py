"""Bounded JSON and atomic derivative-directory writes for artwork handoffs."""

import json
import os
from pathlib import Path
import shutil
import tempfile

MAX_BYTES = 16 * 1024 * 1024


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("JSON input missing or exceeds size limit")

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("duplicate JSON key")
            result[k] = v
        return result

    return json.loads(
        path.read_bytes(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )


def check_destination(destination, protected=()):
    raw = Path(destination).absolute()
    if any(
        p.is_symlink() or getattr(p, "is_junction", lambda: False)()
        for p in (raw, *raw.parents)
    ):
        raise ValueError("output path cannot traverse symlinks/junctions")
    dest = raw.resolve()
    if dest == dest.parent:
        raise ValueError("output cannot be a filesystem root")
    for original in protected:
        p = Path(original).resolve()
        if (
            p == dest
            or p.is_relative_to(dest)
            or (p.is_dir() and dest.is_relative_to(p))
        ):
            raise ValueError("output must not overlap original inputs")
    return dest


def _remove_owned(path, parent):
    path = Path(path)
    if (
        path.resolve().parent != parent.resolve()
        or not path.name.startswith(".artwork-")
        or path.is_symlink()
    ):
        raise ValueError("refusing cleanup outside owned staging directory")
    if path.exists():
        shutil.rmtree(path)


def atomic_directory(destination, build, *, overwrite=False, protected=()):
    dest = check_destination(destination, protected)
    if dest.exists() and (not overwrite or not dest.is_dir()):
        raise ValueError("output exists; explicit overwrite required")
    if dest.exists() and not any(
        (dest / name).is_file() for name in ("layout-handoff.json", "design.json")
    ):
        raise ValueError("overwrite requires a recognized artwork export directory")
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".artwork-stage-", dir=dest.parent))
    backup = None
    try:
        build(stage)
        if dest.exists():
            backup = Path(tempfile.mkdtemp(prefix=".artwork-backup-", dir=dest.parent))
            backup.rmdir()
            if (
                backup.resolve().parent != dest.parent
                or dest.resolve().parent != dest.parent
            ):
                raise ValueError("unsafe rename target")
            os.replace(dest, backup)
        try:
            os.replace(stage, dest)
        except BaseException:
            if backup is not None:
                os.replace(backup, dest)
                backup = None
            raise
    finally:
        _remove_owned(stage, dest.parent)
        if backup is not None:
            _remove_owned(backup, dest.parent)
    return dest
