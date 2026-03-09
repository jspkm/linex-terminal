"""Firestore persistence layer for profile catalogs, optimizations, and incentive sets.

Centralizes Firebase initialization and provides CRUD operations for all three
collections. Reuses the Firebase Admin SDK init pattern from cards/catalog.py.
"""

from __future__ import annotations

import datetime
import uuid

import firebase_admin
from firebase_admin import credentials, firestore, get_app

from google.cloud.firestore_v1.base_query import FieldFilter

from config import FIREBASE_CREDENTIALS_PATH
from models.profile_catalog import ProfileCatalog
from models.incentive_set import IncentiveSet


def _get_db():
    """Get Firestore client, initializing Firebase if needed."""
    import os
    try:
        get_app()
    except ValueError:
        if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            try:
                firebase_admin.initialize_app(cred)
            except ValueError:
                # Another thread/process initialized already.
                pass
        else:
            try:
                firebase_admin.initialize_app()  # Uses Application Default Credentials (Cloud Run)
            except ValueError:
                pass
    return firestore.client()


def _serialize_dates(obj):
    """Recursively convert Firestore DatetimeWithNanoseconds to ISO strings."""
    from google.api_core.datetime_helpers import DatetimeWithNanoseconds

    if isinstance(obj, dict):
        return {k: _serialize_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_dates(i) for i in obj]
    elif isinstance(obj, (DatetimeWithNanoseconds, datetime.datetime)):
        return obj.isoformat()
    return obj


# ---------- Profile Catalogs ----------

CATALOG_COLLECTION = "profile_catalogs"


def fs_save_catalog(catalog: ProfileCatalog) -> str:
    """Save a ProfileCatalog to Firestore. Returns the version string."""
    db = _get_db()
    data = catalog.model_dump(mode="json")
    db.collection(CATALOG_COLLECTION).document(catalog.version).set(data)
    return catalog.version


def fs_load_catalog(version: str) -> ProfileCatalog | None:
    """Load a ProfileCatalog by version. Returns None if not found."""
    db = _get_db()
    doc = db.collection(CATALOG_COLLECTION).document(version).get()
    if not doc.exists:
        return None
    data = _serialize_dates(doc.to_dict())
    return ProfileCatalog.model_validate(data)


def fs_list_catalogs() -> list[dict]:
    """List all catalog versions with basic metadata, newest first."""
    db = _get_db()
    docs = db.collection(CATALOG_COLLECTION).stream()
    results = []
    for doc in docs:
        data = _serialize_dates(doc.to_dict())
        results.append({
            "version": data.get("version", doc.id),
            "created_at": data.get("created_at", ""),
            "k": data.get("k", 0),
            "source": data.get("source", ""),
            "profile_count": len(data.get("profiles", [])),
        })
    results.sort(key=lambda c: c["created_at"] or "", reverse=True)
    return results


def fs_delete_catalog(version: str) -> bool:
    """Delete a catalog by version. Returns True if it existed."""
    db = _get_db()
    doc_ref = db.collection(CATALOG_COLLECTION).document(version)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    doc_ref.delete()
    return True


# ---------- Optimizations ----------

OPTIMIZATION_COLLECTION = "optimizations"
LEGACY_EXPERIMENT_COLLECTION = "experiments"


def fs_save_experiment(state) -> str:
    """Save an ExperimentState to Firestore. Returns the experiment_id."""
    db = _get_db()
    data = state.model_dump(mode="json")
    db.collection(OPTIMIZATION_COLLECTION).document(state.experiment_id).set(data)
    return state.experiment_id


def fs_load_experiment(experiment_id: str):
    """Load an ExperimentState by ID. Returns None if not found."""
    from profile_generator.experiment import ExperimentState

    db = _get_db()
    doc = db.collection(OPTIMIZATION_COLLECTION).document(experiment_id).get()
    if not doc.exists:
        doc = db.collection(LEGACY_EXPERIMENT_COLLECTION).document(experiment_id).get()
    if not doc.exists:
        return None
    data = _serialize_dates(doc.to_dict())
    return ExperimentState.model_validate(data)


def fs_list_experiments(catalog_version: str | None = None) -> list[dict]:
    """List saved optimizations, optionally filtered by catalog_version.

    Reads both `optimizations` and legacy `experiments` collections and
    de-duplicates by experiment_id (prefers optimizations when both exist).
    """
    db = _get_db()
    results_by_id: dict[str, dict] = {}
    for collection_name in [LEGACY_EXPERIMENT_COLLECTION, OPTIMIZATION_COLLECTION]:
        query = db.collection(collection_name)
        if catalog_version:
            query = query.where(filter=FieldFilter("catalog_version", "==", catalog_version))
        docs = query.stream()
        for doc in docs:
            data = _serialize_dates(doc.to_dict())
            exp_id = data.get("experiment_id", doc.id)
            results_by_id[exp_id] = {
                "experiment_id": exp_id,
                "catalog_version": data.get("catalog_version", ""),
                "status": data.get("status", ""),
                "started_at": data.get("started_at", ""),
                "completed_at": data.get("completed_at", ""),
                "result_count": len(data.get("results", [])),
            }
    results = list(results_by_id.values())
    results.sort(
        key=lambda e: e.get("completed_at") or e.get("started_at") or "",
        reverse=True,
    )
    return results


def fs_delete_experiment(experiment_id: str) -> bool:
    """Delete an experiment by ID. Returns True if it existed."""
    db = _get_db()
    deleted = False
    for collection_name in [OPTIMIZATION_COLLECTION, LEGACY_EXPERIMENT_COLLECTION]:
        doc_ref = db.collection(collection_name).document(experiment_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            deleted = True
    return deleted


# ---------- Incentive Sets ----------

INCENTIVE_SET_COLLECTION = "incentive_sets"


def fs_save_incentive_set(incentive_set: IncentiveSet) -> str:
    """Save an IncentiveSet to Firestore. Returns the version string."""
    db = _get_db()
    data = incentive_set.model_dump(mode="json")
    db.collection(INCENTIVE_SET_COLLECTION).document(incentive_set.version).set(data)
    return incentive_set.version


def fs_load_incentive_set(version: str) -> IncentiveSet | None:
    """Load an IncentiveSet by version. Returns None if not found."""
    db = _get_db()
    doc = db.collection(INCENTIVE_SET_COLLECTION).document(version).get()
    if not doc.exists:
        return None
    data = _serialize_dates(doc.to_dict())
    return IncentiveSet.model_validate(data)


def fs_list_incentive_sets() -> list[dict]:
    """List all incentive set versions with metadata, newest first."""
    db = _get_db()
    docs = db.collection(INCENTIVE_SET_COLLECTION).stream()
    results = []
    for doc in docs:
        data = _serialize_dates(doc.to_dict())
        results.append({
            "version": data.get("version", doc.id),
            "created_at": data.get("created_at", ""),
            "name": data.get("name", ""),
            "is_default": data.get("is_default", False),
            "incentive_count": data.get("incentive_count", 0),
        })
    results.sort(key=lambda s: s["created_at"] or "", reverse=True)
    return results


def fs_get_default_incentive_set() -> IncentiveSet | None:
    """Load the current default incentive set."""
    db = _get_db()
    docs = (
        db.collection(INCENTIVE_SET_COLLECTION)
        .where(filter=FieldFilter("is_default", "==", True))
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = _serialize_dates(doc.to_dict())
        return IncentiveSet.model_validate(data)
    return None


def fs_set_default_incentive_set(version: str) -> bool:
    """Set a specific incentive set as the default (clears old default atomically)."""
    db = _get_db()

    # Verify the target exists
    target_ref = db.collection(INCENTIVE_SET_COLLECTION).document(version)
    target = target_ref.get()
    if not target.exists:
        return False

    # Clear any existing defaults
    old_defaults = (
        db.collection(INCENTIVE_SET_COLLECTION)
        .where(filter=FieldFilter("is_default", "==", True))
        .stream()
    )
    batch = db.batch()
    for old_doc in old_defaults:
        batch.update(
            db.collection(INCENTIVE_SET_COLLECTION).document(old_doc.id),
            {"is_default": False},
        )
    # Set the new default
    batch.update(target_ref, {"is_default": True})
    batch.commit()
    return True


def fs_delete_incentive_set(version: str) -> bool:
    """Delete an incentive set. Returns True if it existed."""
    db = _get_db()
    doc_ref = db.collection(INCENTIVE_SET_COLLECTION).document(version)
    doc = doc_ref.get()
    if not doc.exists:
        return False
    doc_ref.delete()
    return True


# ---------- Test Users ----------

TEST_USERS_COLLECTION = "test_users"


def fs_save_test_user(customer_id: str, csv_text: str,
                      country: str = "", transaction_count: int = 0) -> str:
    """Save a test user's CSV data to Firestore. Returns customer_id."""
    db = _get_db()
    db.collection(TEST_USERS_COLLECTION).document(customer_id).set({
        "customer_id": customer_id,
        "country": country,
        "transaction_count": transaction_count,
        "csv_text": csv_text,
    })
    return customer_id


def fs_list_test_user_ids() -> list[str]:
    """Return sorted list of all test user customer IDs."""
    db = _get_db()
    docs = db.collection(TEST_USERS_COLLECTION).stream()
    ids = [doc.id for doc in docs]
    ids.sort()
    return ids


def fs_load_test_user_csv(customer_id: str) -> str | None:
    """Load a test user's CSV text from Firestore. Returns None if not found."""
    db = _get_db()
    doc = db.collection(TEST_USERS_COLLECTION).document(customer_id).get()
    if not doc.exists:
        return None
    return doc.to_dict().get("csv_text")


def fs_load_all_test_user_csvs() -> dict[str, str]:
    """Load all test user CSV texts from Firestore. Returns {customer_id: csv_text}."""
    db = _get_db()
    docs = db.collection(TEST_USERS_COLLECTION).stream()
    result = {}
    for doc in docs:
        data = doc.to_dict()
        csv_text = data.get("csv_text")
        if csv_text:
            result[doc.id] = csv_text
    return result


# ---------- Portfolio Datasets ----------

UPLOADED_TRAINING_DATASET_COLLECTION = "portfolio_datasets"


def fs_save_uploaded_training_dataset(
    upload_name: str,
    transactions: list[dict] | None = None,
    csv_text: str = "",
    parsed_user_count: int = 0,
    parsed_transaction_count: int = 0,
) -> str:
    """Persist uploaded training rows and metadata. Returns dataset_id."""
    db = _get_db()
    dataset_id = f"upl_{uuid.uuid4().hex[:16]}"
    now_iso = datetime.datetime.utcnow().isoformat()
    upload_name = upload_name.strip()

    transactions = transactions or []

    # Store metadata on parent doc; raw content is chunked in subcollection docs
    dataset_ref = db.collection(UPLOADED_TRAINING_DATASET_COLLECTION).document(dataset_id)
    field_names: list[str] = []
    row_count = 0
    storage_format = "rows"
    if csv_text:
        import csv
        import io
        reader = csv.DictReader(io.StringIO(csv_text))
        row_count = 0
        for _ in reader:
            row_count += 1
        field_names = list(reader.fieldnames or [])
        storage_format = "csv_text"
    elif transactions and isinstance(transactions[0], dict):
        row_count = len(transactions)
        field_names = sorted(str(k) for k in transactions[0].keys())

    dataset_ref.set({
        "dataset_id": dataset_id,
        "upload_name": upload_name,
        "created_at": now_iso,
        "row_count": row_count,
        "storage_format": storage_format,
        "field_names": field_names,
        "parsed_user_count": parsed_user_count,
        "parsed_transaction_count": parsed_transaction_count,
    })

    if csv_text:
        # Firestore document limit is 1 MiB; keep chunks well below that.
        chunk_size = 800_000
        for idx in range(0, len(csv_text), chunk_size):
            chunk_text = csv_text[idx: idx + chunk_size]
            chunk_id = f"chunk_{idx // chunk_size:05d}"
            dataset_ref.collection("csv_chunks").document(chunk_id).set({
                "chunk_id": chunk_id,
                "start_index": idx,
                "char_count": len(chunk_text),
                "csv_text": chunk_text,
            })
    else:
        # Keep each chunk document small to avoid Firestore document size limits.
        chunk_size = 500
        for idx in range(0, len(transactions), chunk_size):
            chunk_rows = transactions[idx: idx + chunk_size]
            chunk_id = f"chunk_{idx // chunk_size:05d}"
            dataset_ref.collection("rows").document(chunk_id).set({
                "chunk_id": chunk_id,
                "start_index": idx,
                "row_count": len(chunk_rows),
                "rows": chunk_rows,
            })

    return dataset_id


def fs_list_uploaded_training_datasets() -> list[dict]:
    """List uploaded training datasets, newest first."""
    db = _get_db()
    docs = db.collection(UPLOADED_TRAINING_DATASET_COLLECTION).stream()
    results: list[dict] = []
    for doc in docs:
        data = _serialize_dates(doc.to_dict() or {})
        results.append({
            "dataset_id": data.get("dataset_id", doc.id),
            "upload_name": data.get("upload_name", ""),
            "created_at": data.get("created_at", ""),
            "row_count": data.get("row_count", 0),
            "parsed_user_count": data.get("parsed_user_count", 0),
            "parsed_transaction_count": data.get("parsed_transaction_count", 0),
            "storage_format": data.get("storage_format", "rows"),
        })
    results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return results


def fs_load_uploaded_training_dataset(dataset_id: str) -> dict | None:
    """Load a persisted uploaded dataset by ID.

    Returns a dict with metadata and either `csv_text` and/or `rows`.
    """
    db = _get_db()
    dataset_ref = db.collection(UPLOADED_TRAINING_DATASET_COLLECTION).document(dataset_id)
    doc = dataset_ref.get()
    if not doc.exists:
        return None

    data = _serialize_dates(doc.to_dict() or {})
    storage_format = data.get("storage_format", "rows")
    result = {
        "dataset_id": data.get("dataset_id", dataset_id),
        "upload_name": data.get("upload_name", ""),
        "created_at": data.get("created_at", ""),
        "row_count": data.get("row_count", 0),
        "parsed_user_count": data.get("parsed_user_count", 0),
        "parsed_transaction_count": data.get("parsed_transaction_count", 0),
        "storage_format": storage_format,
    }

    if storage_format == "csv_text":
        chunks = list(dataset_ref.collection("csv_chunks").stream())
        chunk_rows: list[dict] = []
        for c in chunks:
            chunk_rows.append(c.to_dict() or {})
        chunk_rows.sort(key=lambda c: c.get("start_index", 0))
        result["csv_text"] = "".join(str(c.get("csv_text", "")) for c in chunk_rows)
        return result

    chunks = list(dataset_ref.collection("rows").stream())
    chunk_rows: list[dict] = []
    for c in chunks:
        chunk_rows.append(c.to_dict() or {})
    chunk_rows.sort(key=lambda c: c.get("start_index", 0))
    rows: list[dict] = []
    for c in chunk_rows:
        part = c.get("rows", [])
        if isinstance(part, list):
            rows.extend(part)
    result["rows"] = rows
    return result


def fs_delete_portfolio_dataset_cascade(dataset_id: str) -> dict | None:
    """Delete a portfolio dataset and all associated catalogs/optimizations.

    Returns None if dataset doesn't exist, otherwise deletion counts.
    """
    db = _get_db()
    dataset_ref = db.collection(UPLOADED_TRAINING_DATASET_COLLECTION).document(dataset_id)
    dataset_doc = dataset_ref.get()
    if not dataset_doc.exists:
        return None

    # Delete dataset chunks first
    deleted_chunk_docs = 0
    for sub_name in ["rows", "csv_chunks"]:
        for doc in dataset_ref.collection(sub_name).stream():
            doc.reference.delete()
            deleted_chunk_docs += 1

    # Find catalogs trained from this dataset
    catalog_docs = (
        db.collection(CATALOG_COLLECTION)
        .where(filter=FieldFilter("upload_dataset_id", "==", dataset_id))
        .stream()
    )
    catalog_versions: list[str] = []
    for cdoc in catalog_docs:
        catalog_versions.append(cdoc.id)

    deleted_experiments = 0
    for version in catalog_versions:
        seen_ids: set[str] = set()
        for collection_name in [OPTIMIZATION_COLLECTION, LEGACY_EXPERIMENT_COLLECTION]:
            exp_docs = (
                db.collection(collection_name)
                .where(filter=FieldFilter("catalog_version", "==", version))
                .stream()
            )
            for edoc in exp_docs:
                if edoc.id in seen_ids:
                    continue
                seen_ids.add(edoc.id)
                edoc.reference.delete()
                deleted_experiments += 1

    deleted_catalogs = 0
    for version in catalog_versions:
        db.collection(CATALOG_COLLECTION).document(version).delete()
        deleted_catalogs += 1

    dataset_ref.delete()

    orphan_cleanup = fs_delete_orphaned_portfolio_artifacts()

    return {
        "dataset_id": dataset_id,
        "deleted_dataset": True,
        "deleted_chunk_docs": deleted_chunk_docs,
        "deleted_catalogs": deleted_catalogs,
        "deleted_experiments": deleted_experiments,
        "deleted_orphan_catalogs": orphan_cleanup.get("deleted_catalogs", 0),
        "deleted_orphan_experiments": orphan_cleanup.get("deleted_experiments", 0),
    }


def fs_delete_orphaned_portfolio_artifacts() -> dict:
    """Delete upload-derived catalogs/optimizations that no longer map to a dataset."""
    db = _get_db()

    dataset_ids: set[str] = set()
    for ddoc in db.collection(UPLOADED_TRAINING_DATASET_COLLECTION).stream():
        dataset_ids.add(ddoc.id)

    orphan_catalog_versions: list[str] = []
    for cdoc in db.collection(CATALOG_COLLECTION).stream():
        data = _serialize_dates(cdoc.to_dict() or {})
        source = str(data.get("source", "") or "")
        if not source.startswith("upload:"):
            continue
        upload_dataset_id = str(data.get("upload_dataset_id", "") or "")
        if not upload_dataset_id or upload_dataset_id not in dataset_ids:
            orphan_catalog_versions.append(cdoc.id)

    deleted_experiments = 0
    for version in orphan_catalog_versions:
        seen_ids: set[str] = set()
        for collection_name in [OPTIMIZATION_COLLECTION, LEGACY_EXPERIMENT_COLLECTION]:
            exp_docs = (
                db.collection(collection_name)
                .where(filter=FieldFilter("catalog_version", "==", version))
                .stream()
            )
            for edoc in exp_docs:
                if edoc.id in seen_ids:
                    continue
                seen_ids.add(edoc.id)
                edoc.reference.delete()
                deleted_experiments += 1

    deleted_catalogs = 0
    for version in orphan_catalog_versions:
        db.collection(CATALOG_COLLECTION).document(version).delete()
        deleted_catalogs += 1

    return {
        "deleted_catalogs": deleted_catalogs,
        "deleted_experiments": deleted_experiments,
    }
