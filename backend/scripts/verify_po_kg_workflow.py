"""Verify £25k PO workflow uses system KG impact and overlay graph."""

import json
import sys
from urllib import error, request

API_BASE = "http://127.0.0.1:8000"
GOLDEN_TEXT = (
    "From next quarter, all purchase orders above £25,000 must require finance approval "
    "before supplier confirmation. The system must log who approved it and block confirmation "
    "if approval is missing."
)


def api_call(method: str, path: str, payload: dict | None = None) -> dict:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = request.Request(f"{API_BASE}{path}", data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as http_error:
        detail = http_error.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed: {http_error.code} {detail}") from http_error


def main() -> int:
    ingest = api_call("POST", "/api/systems/ingest")
    print(f"Ingested {ingest['succeeded']}/{ingest['total']} systems")

    classify = api_call("POST", "/api/change/classify", {"text": GOLDEN_TEXT})
    session_id = classify["session_id"]
    systems = classify.get("systems") or {}
    print(f"Session: {session_id}")
    print(f"Primary system: {systems.get('primary_system_id')}")
    print(f"Identified systems: {[item['system_id'] for item in systems.get('systems', [])]}")

    api_call(
        "POST",
        "/api/systems/confirm",
        {"session_id": session_id, "system_ids": [systems.get("primary_system_id", "erpnext")]},
    )

    contract = api_call("POST", "/api/contract/generate", {"text": GOLDEN_TEXT, "session_id": session_id})
    api_call(
        "POST",
        "/api/contract/approve",
        {"session_id": session_id, "contract_yaml": contract["contract_yaml"]},
    )

    impact = api_call("POST", "/api/impact/analyze", {"session_id": session_id})
    print(f"Impacted files: {len(impact['files'])}")
    for file_entry in impact["files"][:3]:
        print(f"  - {file_entry['path']} (score={file_entry['score']})")

    graph = api_call("GET", f"/api/graph/current?session_id={session_id}")
    overlay_nodes = [node for node in graph["nodes"] if node["type"] == "SystemKGFile"]
    target_nodes = [node for node in graph["nodes"] if node["type"] == "TargetSystem"]
    print(f"Overlay SystemKGFile nodes: {len(overlay_nodes)}")
    print(f"TargetSystem nodes: {len(target_nodes)}")
    if overlay_nodes:
        print(f"First overlay kg_node_id: {overlay_nodes[0]['metadata'].get('kg_node_id')}")
        print(f"First overlay impact_source: {overlay_nodes[0]['metadata'].get('impact_source')}")

    erpnext_graph = api_call("GET", "/api/systems/graph?system_id=erpnext")
    print(f"ERPNext KG nodes: {len(erpnext_graph['nodes'])}")

    if systems.get("primary_system_id") != "erpnext":
        print("FAIL: ERPNext not identified as primary system")
        return 1
    if not any("erpnext:" in file_entry["path"] for file_entry in impact["files"]):
        print("WARN: No erpnext-prefixed impact paths (may still be KG-backed)")
    if not overlay_nodes:
        print("FAIL: No change overlay nodes linked to system KG")
        return 1
    print("PASS: ERPNext identified and change overlay graph linked to system KG")
    return 0


if __name__ == "__main__":
    sys.exit(main())
