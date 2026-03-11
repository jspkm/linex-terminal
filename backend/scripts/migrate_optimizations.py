#!/usr/bin/env python3
"""One-time migration: copy Firestore documents from `experiments` to `optimizations`.

Usage:
    cd backend
    python scripts/migrate_experiments_to_optimizations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import local_write_safety_error  # noqa: E402
from profile_generator.firestore_client import (  # noqa: E402
    _get_db,
    LEGACY_EXPERIMENT_COLLECTION,
    OPTIMIZATION_COLLECTION,
)


def migrate() -> None:
    db = _get_db()
    source = db.collection(LEGACY_EXPERIMENT_COLLECTION).stream()

    copied = 0
    skipped = 0
    for doc in source:
        target_ref = db.collection(OPTIMIZATION_COLLECTION).document(doc.id)
        if target_ref.get().exists:
            skipped += 1
            continue
        target_ref.set(doc.to_dict() or {})
        copied += 1

    print(f"Copied: {copied}")
    print(f"Skipped (already exists): {skipped}")
    print("Migration complete.")


if __name__ == "__main__":
    safety_error = local_write_safety_error()
    if safety_error:
        print(f"Startup: FAILED\nReason:  {safety_error}")
        sys.exit(1)
    migrate()
