"""Report config CRUD handler logic.

Each handler returns a plain (dict, int) tuple.
Heavy imports are deferred inside functions to minimize cold-start latency.
"""

from handlers._common import handler


@handler
def handle_save_report_config(data: dict) -> tuple[dict, int]:
    """Save a report configuration."""
    from profile_generator.firestore_client import fs_save_report_config

    name = (data.get("name") or "").strip()
    columns = data.get("columns", [])
    charts = data.get("charts", [])
    layout = data.get("layout", {})
    if not name:
        return {"error": "Missing config name"}, 400
    config = fs_save_report_config(name, columns, charts=charts, layout=layout)
    return config, 200


@handler
def handle_list_report_configs() -> tuple[dict, int]:
    """List all saved report configs."""
    from profile_generator.firestore_client import fs_list_report_configs

    configs = fs_list_report_configs()
    return {"configs": configs}, 200


@handler
def handle_load_report_config(config_id: str) -> tuple[dict, int]:
    """Load a report config by ID."""
    from profile_generator.firestore_client import fs_load_report_config

    if not config_id:
        return {"error": "Missing config_id"}, 400
    config = fs_load_report_config(config_id)
    if not config:
        return {"error": "Report config not found"}, 404
    return config, 200


@handler
def handle_delete_report_config(config_id: str) -> tuple[dict, int]:
    """Delete a report config."""
    from profile_generator.firestore_client import fs_delete_report_config

    if not config_id:
        return {"error": "Missing config_id"}, 400
    ok = fs_delete_report_config(config_id)
    if not ok:
        return {"error": "Report config not found"}, 404
    return {"deleted": True}, 200
