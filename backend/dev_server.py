"""Local development server that serves all Cloud Functions via Flask.

This bypasses the Firebase emulator's buggy Python worker lifecycle by
running a single Flask process with all endpoints registered.

Usage:
    source venv/bin/activate
    python dev_server.py
"""

import json
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime

# Ensure env vars loaded before imports
from config import GEMINI_API_KEY, MODEL

from analysis.feature_engine import compute_features
from analysis.preprocessor import (
    clean_transactions,
    load_test_user,
    parse_json_transactions,
    parse_portfolio_records,
)
from cards.catalog import CardCatalog
from config import CARDS_PATH, TEST_USERS_DIR
from utils.formatters import format_features_for_llm, format_cards_for_llm, format_profiles_for_llm
from profile_generator.versioning import get_latest_catalog
from prompts.profiling import SYSTEM_PROMPT as PROF_SYSTEM, build_user_prompt as prof_prompt
from prompts.card_matching import SYSTEM_PROMPT as CARD_SYSTEM, build_user_prompt as card_prompt
from analysis.profiler import _parse_toon_profile
from analysis.card_matcher import _parse_toon_recommendations

from google import genai
from google.genai import types

_catalog = CardCatalog(str(CARDS_PATH))
_gemini = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)
CORS(app)


def _strip_fences(raw: str) -> str:
    """Strip markdown code fences if present."""
    if not raw.startswith("```"):
        return raw
    lines = raw.split("\n")
    clean = []
    in_block = False
    for line in lines:
        if line.startswith("```") and not in_block:
            in_block = True
            continue
        if line.startswith("```") and in_block:
            break
        if in_block:
            clean.append(line)
    return "\n".join(clean)


def _llm_call(system: str, user_content: str) -> str:
    """Make a Gemini API call and return the text response."""
    response = _gemini.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            max_output_tokens=4000,
        )
    )
    return response.text.strip()


def _analyze_pipeline(features, assignment, catalog, region=None):
    """Run profile + match cards sequentially with Gemini."""
    features_toon = format_features_for_llm(features)

    profiles_toon = format_profiles_for_llm(assignment) if assignment else "assigned_profile: unknown"

    region_val = region or features.country
    cards = catalog.get_cards_for_region(region_val)
    if not cards:
        cards = catalog.cards
    cards_toon = format_cards_for_llm(cards)

    raw_resp = _llm_call(PROF_SYSTEM, prof_prompt(features_toon, profiles_toon, cards_toon))
    raw_resp = _strip_fences(raw_resp)
    
    profile = _parse_toon_profile(raw_resp, features.customer_id)
    rec = _parse_toon_recommendations(raw_resp, features.customer_id)

    return profile, rec


def _analyze_streaming(features, assignment, catalog, region=None):
    """Run profile + match with streaming progress via SSE."""
    features_toon = format_features_for_llm(features)
    
    profiles_toon = format_profiles_for_llm(assignment) if assignment else "assigned_profile: unknown"

    region_val = region or features.country
    cards = catalog.get_cards_for_region(region_val)
    if not cards:
        cards = catalog.cards
    cards_toon = format_cards_for_llm(cards)

    def generate():
        yield f"data: {json.dumps({'step': 'profiling', 'message': 'Profiling and matching with Gemini...'})}\n\n"

        raw_resp = _llm_call(PROF_SYSTEM, prof_prompt(features_toon, profiles_toon, cards_toon))
        raw_resp = _strip_fences(raw_resp)
        
        profile = _parse_toon_profile(raw_resp, features.customer_id)
        rec = _parse_toon_recommendations(raw_resp, features.customer_id)

        yield f"data: {json.dumps({'step': 'done', 'result': {'profile': profile.model_dump(), 'features': features.model_dump(mode='json'), 'card_recommendations': rec.model_dump()}})}\n\n"

    return generate


@app.route("/linexonewhitelabeler/us-central1/list_test_users", methods=["GET"])
def list_test_users():
    if not TEST_USERS_DIR.exists():
        return jsonify({"user_ids": []})
    ids = []
    for f in sorted(TEST_USERS_DIR.iterdir()):
        if f.name.startswith("test-user-") and f.name.endswith(".csv"):
            uid = f.name.replace("test-user-", "").replace(".csv", "")
            ids.append(uid)
    return jsonify({"user_ids": ids[:20]})


@app.route("/linexonewhitelabeler/us-central1/analyze_test_user", methods=["POST"])
def analyze_test_user():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", "")
        stream = data.get("stream", False)
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        user_txns = load_test_user(user_id)
        clean = clean_transactions(user_txns)
        features = compute_features(clean)
        
        profile_catalog = get_latest_catalog()
        assignment = None
        if profile_catalog:
            assignment = _assign_profile(clean, profile_catalog, eval_date=profile_catalog.dataset_max_date)

        if stream:
            gen = _analyze_streaming(features, assignment, _catalog)
            return Response(gen(), content_type="text/event-stream")

        profile, rec = _analyze_pipeline(features, assignment, _catalog)
        return jsonify({
            "profile": profile.model_dump(),
            "features": features.model_dump(mode="json"),
            "card_recommendations": rec.model_dump(),
            "assignment": assignment.model_dump(mode="json") if assignment else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/analyze_transactions", methods=["POST"])
def analyze_transactions():
    try:
        data = request.get_json(silent=True) or {}
        transactions = data.get("transactions", [])
        customer_id = data.get("customer_id", "")
        region = data.get("region")
        stream = data.get("stream", False)

        if not transactions:
            return jsonify({"error": "No transactions provided"}), 400

        user_txns = parse_json_transactions(transactions, customer_id)
        clean = clean_transactions(user_txns)
        features = compute_features(clean)
        
        profile_catalog = get_latest_catalog()
        assignment = None
        if profile_catalog:
            assignment = _assign_profile(clean, profile_catalog, eval_date=profile_catalog.dataset_max_date)

        if stream:
            gen = _analyze_streaming(features, assignment, _catalog, region)
            return Response(gen(), content_type="text/event-stream")

        profile, rec = _analyze_pipeline(features, assignment, _catalog, region)
        return jsonify({
            "profile": profile.model_dump(),
            "features": features.model_dump(mode="json"),
            "card_recommendations": rec.model_dump(),
            "assignment": assignment.model_dump(mode="json") if assignment else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/ask_test_user", methods=["POST"])
def ask_test_user():
    try:
        if not GEMINI_API_KEY:
            return jsonify({"error": "GEMINI_API_KEY not configured"}), 500

        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", "")
        question = data.get("question", "")

        if not user_id or not question:
            return jsonify({"error": "Missing user_id or question"}), 400

        user_txns = load_test_user(user_id)
        clean = clean_transactions(user_txns)
        features = compute_features(clean)
        features_toon = format_features_for_llm(features)

        system = (
            "You are a financial analyst for the Linex loyalty platform. "
            "Given a user's spending data (in TOON format), answer the question. "
            "Be specific, cite evidence from the data, and state your confidence level."
        )
        answer = _llm_call(system, f"Based on this spending data:\n\n{features_toon}\n\nQuestion: {question}")

        return jsonify({
            "question": question,
            "answer": answer,
            "user_id": user_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/ask_qu", methods=["POST"])
def ask_qu():
    try:
        if not GEMINI_API_KEY:
            return jsonify({"error": "GEMINI_API_KEY not configured"}), 500

        data = request.get_json(silent=True) or {}
        transactions = data.get("transactions", [])
        question = data.get("question", "")
        customer_id = data.get("customer_id", "")

        if not transactions or not question:
            return jsonify({"error": "Missing transactions or question"}), 400

        user_txns = parse_json_transactions(transactions, customer_id)
        clean = clean_transactions(user_txns)
        features = compute_features(clean)
        features_toon = format_features_for_llm(features)

        system = (
            "You are a financial analyst for the Linex loyalty platform. "
            "Given a user's spending data (in TOON format), answer the question. "
            "Be specific, cite evidence from the data, and state your confidence level."
        )
        answer = _llm_call(system, f"Based on this spending data:\n\n{features_toon}\n\nQuestion: {question}")

        return jsonify({
            "question": question,
            "answer": answer,
            "customer_id": customer_id,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Profile Generator ----------
import csv
import io
from config import TEST_USERS_DIR, DEFAULT_K, DEFAULT_TIME_WINDOW
from analysis.preprocessor import parse_csv_transactions, clean_transactions as clean_txns_fn
from profile_generator.feature_derivation import derive_batch_features
from profile_generator.trainer import learn_profiles as _learn_profiles
from profile_generator.assigner import assign_profile as _assign_profile
from profile_generator.versioning import (
    save_catalog, load_catalog, list_catalogs, get_latest_catalog, fork_catalog, delete_catalog,
)
from profile_generator.optimization import (
    start_optimization, get_optimization_status, advance_optimization,
    cancel_optimization, save_optimization, delete_optimization,
    list_optimizations, load_optimization,
)
from profile_generator.incentive_manager import load_or_seed_default, generate_version
from profile_generator.firestore_client import (
    fs_save_incentive_set, fs_load_incentive_set,
    fs_list_incentive_sets, fs_get_default_incentive_set,
    fs_set_default_incentive_set, fs_delete_incentive_set,
    fs_save_portfolio_dataset, fs_list_portfolio_datasets,
    fs_load_portfolio_dataset, fs_delete_portfolio_dataset_cascade,
)
from models.incentive_set import Incentive, IncentiveSet
from models.transaction import UserTransactions


def _load_all_test_users() -> dict[str, UserTransactions]:
    """Load all test users from data/test-users/."""
    users: dict[str, UserTransactions] = {}
    if not TEST_USERS_DIR.exists():
        return users
    for f in sorted(TEST_USERS_DIR.iterdir()):
        if f.name.startswith("test-user-") and f.name.endswith(".csv"):
            uid = f.name.replace("test-user-", "").replace(".csv", "")
            csv_text = f.read_text(encoding="utf-8")
            user_txns = parse_csv_transactions(csv_text, customer_id=uid)
            users[uid] = user_txns
    return users


def _load_retail_users(limit: int = 0) -> dict[str, UserTransactions]:
    """Load users from retail.csv, grouped by Customer ID."""
    from config import DATA_DIR
    retail_path = DATA_DIR / "retail.csv"
    if not retail_path.exists():
        return {}

    users_txns: dict[str, list] = {}
    with open(retail_path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cid = row.get("Customer ID", "").strip()
            if not cid or cid == "":
                continue
            # Clean float CIDs like "13085.0"
            try:
                cid = str(int(float(cid)))
            except (ValueError, TypeError):
                pass
            if cid not in users_txns:
                users_txns[cid] = []
            users_txns[cid].append(row)

    if limit > 0:
        keys = list(users_txns.keys())[:limit]
        users_txns = {k: users_txns[k] for k in keys}

    result: dict[str, UserTransactions] = {}
    for cid, rows in users_txns.items():
        csv_rows = []
        for r in rows:
            csv_rows.append(r)
        # Build CSV text and parse
        if csv_rows:
            fieldnames = list(csv_rows[0].keys())
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
            result[cid] = parse_csv_transactions(buf.getvalue(), customer_id=cid)

    return result


@app.route("/linexonewhitelabeler/us-central1/learn_profiles", methods=["POST"])
def learn_profiles_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        source = str(data.get("source", "test-users") or "test-users")
        k = data.get("k", DEFAULT_K)
        limit = data.get("limit", 0)
        upload_name = str(data.get("upload_name", "")).strip()
        upload_csv_text = str(data.get("csv_text", "") or "")
        upload_transactions = data.get("transactions", [])
        upload_dataset_id = ""

        # Load transactions
        if source == "uploaded":
            raw_rows: list[dict] = []
            if upload_csv_text.strip():
                reader = csv.DictReader(io.StringIO(upload_csv_text))
                raw_rows = [row for row in reader]
            elif isinstance(upload_transactions, list):
                raw_rows = upload_transactions

            if not raw_rows:
                return jsonify({"error": "No uploaded transactions provided"}), 400

            users = parse_portfolio_records(raw_rows, default_customer_id=upload_name)
            if not users:
                return jsonify({"error": "No valid user transactions found in uploaded data"}), 400
            parsed_txn_count = sum(len(u.transactions) for u in users.values())
            upload_dataset_id = fs_save_portfolio_dataset(
                upload_name=upload_name,
                transactions=raw_rows if not upload_csv_text.strip() else None,
                csv_text=upload_csv_text,
                parsed_user_count=len(users),
                parsed_transaction_count=parsed_txn_count,
            )
            source = f"upload:{upload_name}" if upload_name else f"upload:{upload_dataset_id}"
        elif source.startswith("uploaded-dataset:"):
            selected_dataset_id = source.split(":", 1)[1].strip()
            if not selected_dataset_id:
                return jsonify({"error": "Missing uploaded dataset id"}), 400
            dataset = fs_load_portfolio_dataset(selected_dataset_id)
            if not dataset:
                return jsonify({"error": "Uploaded dataset not found"}), 404
            raw_rows: list[dict] = []
            dataset_csv_text = str(dataset.get("csv_text", "") or "")
            if dataset_csv_text:
                reader = csv.DictReader(io.StringIO(dataset_csv_text))
                raw_rows = [row for row in reader]
            elif isinstance(dataset.get("rows"), list):
                raw_rows = dataset.get("rows") or []
            if not raw_rows:
                return jsonify({"error": "Selected uploaded dataset has no rows"}), 400
            users = parse_portfolio_records(raw_rows, default_customer_id="")
            if not users:
                return jsonify({"error": "No valid user transactions found in selected uploaded dataset"}), 400
            upload_dataset_id = selected_dataset_id
            upload_name = str(dataset.get("upload_name", "")).strip()
            source = f"upload:{upload_name}" if upload_name else f"upload:{upload_dataset_id}"
        elif source == "retail":
            users = _load_retail_users(limit=limit)
        else:
            users = _load_all_test_users()

        if not users:
            return jsonify({"error": f"No users found for source '{source}'"}), 400

        # Derive features
        feature_df = derive_batch_features(users)

        if len(feature_df) < 2:
            return jsonify({"error": "Need at least 2 users to learn profiles"}), 400

        global_max: datetime | None = None
        for user_txns in users.values():
            for t in user_txns.transactions:
                if global_max is None or t.date > global_max:
                    global_max = t.date

        # Train
        catalog = _learn_profiles(feature_df, k=k, source=source, dataset_max_date=global_max)
        if upload_dataset_id:
            catalog.upload_dataset_id = upload_dataset_id
            catalog.upload_dataset_name = upload_name

        # Save
        save_catalog(catalog)

        return jsonify(catalog.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/assign_profile", methods=["POST"])
def assign_profile_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id", "")
        catalog_version = data.get("catalog_version", "")

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        # Load catalog
        if catalog_version:
            catalog = load_catalog(catalog_version)
        else:
            catalog = get_latest_catalog()
        if not catalog:
            return jsonify({"error": "No profile catalog found"}), 404

        # Load user transactions
        user_txns = load_test_user(user_id)
        clean = clean_txns_fn(user_txns)

        # Assign
        assignment = _assign_profile(clean, catalog, eval_date=catalog.dataset_max_date)
        return jsonify(assignment.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/profile_catalog", methods=["GET"])
@app.route("/linexonewhitelabeler/us-central1/profile_catalog/<version>", methods=["GET"])
def get_profile_catalog_endpoint(version=None):
    try:
        if version:
            catalog = load_catalog(version)
        else:
            catalog = get_latest_catalog()

        if not catalog:
            return jsonify({"error": "No catalog found"}), 404

        return jsonify(catalog.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/list_profile_catalogs", methods=["GET"])
def list_profile_catalogs_endpoint():
    try:
        catalogs = list_catalogs()
        return jsonify({"catalogs": catalogs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/list_portfolio_datasets", methods=["GET"])
def list_portfolio_datasets_endpoint():
    try:
        datasets = fs_list_portfolio_datasets()
        return jsonify({"datasets": datasets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route("/linexonewhitelabeler/us-central1/fork_catalog", methods=["POST"])
def fork_catalog_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        source_version = data.get("source_version", "")
        modifications = data.get("modifications")

        if not source_version:
            return jsonify({"error": "Missing source_version"}), 400

        forked = fork_catalog(source_version, modifications)
        if not forked:
            return jsonify({"error": f"Catalog version '{source_version}' not found"}), 404

        return jsonify(forked.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/start_optimize", methods=["POST"])
def start_optimize_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        catalog_version = data.get("catalog_version", "")
        max_iterations = data.get("max_iterations", 50)
        patience = data.get("patience", 3)

        if not catalog_version:
            return jsonify({"error": "Missing catalog_version"}), 400

        incentive_set_version = data.get("incentive_set_version") or None

        optimization_id = start_optimization(
            catalog_version,
            max_iterations=int(max_iterations),
            patience=int(patience),
            incentive_set_version=incentive_set_version,
        )
        return jsonify({"optimization_id": optimization_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/optimize_status/<optimization_id>", methods=["GET"])
def get_optimize_status_endpoint(optimization_id):
    try:
        state = get_optimization_status(optimization_id)
        if not state:
            return jsonify({"error": "Optimization not found"}), 404
        if state.status == "running":
            state = advance_optimization(optimization_id, profiles_per_tick=1) or state
            
        return jsonify(state.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/list_optimizations", methods=["GET"])
def list_optimizations_endpoint():
    try:
        catalog_version = request.args.get("catalog_version")
        optimizations = list_optimizations(catalog_version or None)
        return jsonify({"optimizations": optimizations})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/load_optimize/<optimization_id>", methods=["GET"])
def load_optimize_endpoint(optimization_id):
    try:
        state = load_optimization(optimization_id)
        if not state:
            return jsonify({"error": "Optimization not found"}), 404
        return jsonify(state.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/cancel_optimize/<optimization_id>", methods=["POST"])
def cancel_optimize_endpoint(optimization_id):
    try:
        ok = cancel_optimization(optimization_id)
        if not ok:
            return jsonify({"error": "Optimization not found or not running"}), 404
        return jsonify({"cancelled": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/save_optimize/<optimization_id>", methods=["POST"])
def save_optimize_endpoint(optimization_id):
    try:
        path = save_optimization(optimization_id)
        if not path:
            return jsonify({"error": "Optimization not found or not in a saveable state"}), 404
        return jsonify({"saved": True, "path": path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/delete_optimize/<optimization_id>", methods=["DELETE"])
def delete_optimize_endpoint(optimization_id):
    try:
        ok = delete_optimization(optimization_id)
        if not ok:
            return jsonify({"error": "Optimization not found"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/delete_catalog/<version>", methods=["DELETE"])
def delete_catalog_endpoint(version):
    try:
        ok = delete_catalog(version)
        if not ok:
            return jsonify({"error": "Catalog not found"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/linexonewhitelabeler/us-central1/delete_portfolio_dataset/<dataset_id>", methods=["DELETE"])
def delete_portfolio_dataset_endpoint(dataset_id):
    try:
        result = fs_delete_portfolio_dataset_cascade(dataset_id)
        if not result:
            return jsonify({"error": "Portfolio dataset not found"}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- Incentive Sets ----------

@app.route("/linexonewhitelabeler/us-central1/list_incentive_sets", methods=["GET"])
def list_incentive_sets_endpoint():
    try:
        sets = fs_list_incentive_sets()
        return jsonify({"incentive_sets": sets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/incentive_set", methods=["GET"])
@app.route("/linexonewhitelabeler/us-central1/incentive_set/<version>", methods=["GET"])
def get_incentive_set_endpoint(version=None):
    try:
        if version:
            inc_set = fs_load_incentive_set(version)
        else:
            inc_set = fs_get_default_incentive_set()
            if not inc_set:
                # Auto-seed the default on first access
                inc_set = load_or_seed_default()
        if not inc_set:
            return jsonify({"error": "Incentive set not found"}), 404
        return jsonify(inc_set.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/create_incentive_set", methods=["POST"])
def create_incentive_set_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "")
        description = data.get("description", "")
        raw_incentives = data.get("incentives", [])
        set_as_default = data.get("set_as_default", False)

        if not raw_incentives:
            return jsonify({"error": "No incentives provided"}), 400

        version = generate_version(raw_incentives)
        inc_set = IncentiveSet(
            version=version,
            name=name,
            description=description,
            is_default=set_as_default,
            incentive_count=len(raw_incentives),
            incentives=[Incentive(**inc) for inc in raw_incentives],
        )

        if set_as_default:
            # Clear old default first, then save
            fs_set_default_incentive_set(version)  # will be no-op if doc doesn't exist yet
        fs_save_incentive_set(inc_set)
        if set_as_default:
            fs_set_default_incentive_set(version)

        return jsonify(inc_set.model_dump(mode="json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/set_default_incentive_set/<version>", methods=["POST"])
def set_default_incentive_set_endpoint(version):
    try:
        ok = fs_set_default_incentive_set(version)
        if not ok:
            return jsonify({"error": "Incentive set not found"}), 404
        return jsonify({"default": True, "version": version})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/linexonewhitelabeler/us-central1/delete_incentive_set/<version>", methods=["DELETE"])
def delete_incentive_set_endpoint(version):
    try:
        ok = fs_delete_incentive_set(version)
        if not ok:
            return jsonify({"error": "Incentive set not found"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"Starting local dev server on http://127.0.0.1:5050 (model: {MODEL})")
    print("Functions available:")
    print("  - GET  /linexonewhitelabeler/us-central1/list_test_users")
    print("  - POST /linexonewhitelabeler/us-central1/analyze_test_user")
    print("  - POST /linexonewhitelabeler/us-central1/analyze_transactions")
    print("  - POST /linexonewhitelabeler/us-central1/ask_test_user")
    print("  - POST /linexonewhitelabeler/us-central1/ask_qu")
    print("  Profile Generator:")
    print("  - POST /linexonewhitelabeler/us-central1/learn_profiles")
    print("  - POST /linexonewhitelabeler/us-central1/assign_profile")
    print("  - GET  /linexonewhitelabeler/us-central1/profile_catalog")
    print("  - GET  /linexonewhitelabeler/us-central1/list_profile_catalogs")
    print("  - GET  /linexonewhitelabeler/us-central1/list_portfolio_datasets")
    print("  - POST /linexonewhitelabeler/us-central1/fork_catalog")
    print("  Optimize:")
    print("  - POST /linexonewhitelabeler/us-central1/start_optimize")
    print("  - GET  /linexonewhitelabeler/us-central1/optimize_status/<id>")
    print("  - GET  /linexonewhitelabeler/us-central1/list_optimizations")
    print("  - GET  /linexonewhitelabeler/us-central1/load_optimize/<id>")
    print("  - POST /linexonewhitelabeler/us-central1/cancel_optimize/<id>")
    print("  - POST /linexonewhitelabeler/us-central1/save_optimize/<id>")
    print("  - DEL  /linexonewhitelabeler/us-central1/delete_optimize/<id>")
    print("  - DEL  /linexonewhitelabeler/us-central1/delete_catalog/<version>")
    print("  - DEL  /linexonewhitelabeler/us-central1/delete_portfolio_dataset/<dataset_id>")
    print("  Incentive Sets:")
    print("  - GET  /linexonewhitelabeler/us-central1/list_incentive_sets")
    print("  - GET  /linexonewhitelabeler/us-central1/incentive_set")
    print("  - GET  /linexonewhitelabeler/us-central1/incentive_set/<version>")
    print("  - POST /linexonewhitelabeler/us-central1/create_incentive_set")
    print("  - POST /linexonewhitelabeler/us-central1/set_default_incentive_set/<version>")
    print("  - DEL  /linexonewhitelabeler/us-central1/delete_incentive_set/<version>")
    app.run(host="127.0.0.1", port=5050, debug=False)
