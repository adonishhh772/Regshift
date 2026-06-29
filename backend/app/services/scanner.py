import ast
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.database import get_connection
from app.services.domain_loader import load_domain_pack

SCAN_EXTENSIONS = {".py", ".js", ".ts", ".json", ".html", ".md", ".yml", ".yaml"}
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "env", "dist", "build"}


def get_index_status() -> dict[str, Any]:
    connection = get_connection()
    row = connection.execute("SELECT * FROM index_meta WHERE id = 1").fetchone()
    count = connection.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
    connection.close()

    if row:
        return {
            "status": "ready",
            "file_count": count,
            "source": row["source"],
            "last_scan": row["last_scan"],
        }

    if settings.demo_seed_path.exists():
        return {
            "status": "seed_available",
            "file_count": 0,
            "source": "none",
            "last_scan": None,
        }

    return {
        "status": "missing",
        "file_count": 0,
        "source": "none",
        "last_scan": None,
    }


def scan_index(domain: str = "procurement") -> dict[str, Any]:
    if settings.erpnext_repo_path.exists():
        entries = _scan_repo(settings.erpnext_repo_path, domain)
        source = "erpnext_repo"
    elif settings.demo_seed_path.exists():
        entries = _load_seed()
        source = "demo_seed"
    else:
        raise FileNotFoundError("No ERPNext repo or demo seed available")

    _persist_index(entries, source)
    return {
        "status": "ready",
        "file_count": len(entries),
        "source": source,
        "last_scan": datetime.now(timezone.utc).isoformat(),
    }


def search_index(keywords: list[str], limit: int = 15) -> list[dict[str, Any]]:
    connection = get_connection()
    rows = connection.execute("SELECT * FROM file_index").fetchall()
    connection.close()

    if not rows:
        scan_index()
        connection = get_connection()
        rows = connection.execute("SELECT * FROM file_index").fetchall()
        connection.close()

    scored: list[tuple[float, dict[str, Any]]] = []
    keyword_set = {keyword.lower() for keyword in keywords}

    for row in rows:
        row_dict = dict(row)
        matched_keywords: list[str] = []
        haystack = " ".join(
            [
                row_dict.get("path", ""),
                row_dict.get("content_snippet", ""),
                row_dict.get("keywords", ""),
                row_dict.get("python_functions", ""),
                row_dict.get("python_classes", ""),
            ]
        ).lower()

        for keyword in keyword_set:
            if keyword in haystack:
                matched_keywords.append(keyword)

        if not matched_keywords:
            continue

        score = len(matched_keywords) * 10.0
        if "purchase_order" in row_dict.get("path", "").lower():
            score += 20.0
        if "buying" in row_dict.get("module", "").lower():
            score += 10.0

        row_dict["matched_keywords"] = matched_keywords
        row_dict["score"] = score
        scored.append((score, row_dict))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def _scan_repo(repo_path: Path, domain: str) -> list[dict[str, Any]]:
    pack = load_domain_pack(domain)
    keywords = pack.get("keywords", [])
    entries: list[dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in SCAN_EXTENSIONS:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        relative_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
        entry = _build_index_entry(relative_path, content, keywords, timestamp)
        entries.append(entry)

    return entries


def _load_seed() -> list[dict[str, Any]]:
    with settings.demo_seed_path.open(encoding="utf-8") as file:
        data = json.load(file)
    return data.get("files", data)


def _build_index_entry(
    path: str,
    content: str,
    keywords: list[str],
    timestamp: str,
) -> dict[str, Any]:
    snippet = content[:500].replace("\n", " ")
    matched = [keyword for keyword in keywords if keyword.lower() in content.lower()]
    module = path.split("/")[0] if "/" in path else "root"

    python_classes: list[str] = []
    python_functions: list[str] = []
    imports: list[str] = []

    if path.endswith(".py"):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    python_classes.append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    python_functions.append(node.name)
                elif isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        except SyntaxError:
            pass

    return {
        "path": path,
        "extension": Path(path).suffix,
        "module": module,
        "content_snippet": snippet,
        "keywords": matched,
        "python_classes": python_classes,
        "python_functions": python_functions,
        "imports": imports,
        "business_entities": _detect_entities(content),
        "scan_timestamp": timestamp,
    }


def _detect_entities(content: str) -> list[str]:
    entities = []
    candidates = ["purchase_order", "supplier", "purchase_invoice", "payment", "stock_entry"]
    lower = content.lower()
    for candidate in candidates:
        if candidate in lower:
            entities.append(candidate)
    return entities


def _persist_index(entries: list[dict[str, Any]], source: str) -> None:
    connection = get_connection()
    connection.execute("DELETE FROM file_index")
    for entry in entries:
        connection.execute(
            """
            INSERT OR REPLACE INTO file_index
            (path, extension, module, content_snippet, keywords, python_classes,
             python_functions, imports, business_entities, scan_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["path"],
                entry.get("extension"),
                entry.get("module"),
                entry.get("content_snippet"),
                json.dumps(entry.get("keywords", [])),
                json.dumps(entry.get("python_classes", [])),
                json.dumps(entry.get("python_functions", [])),
                json.dumps(entry.get("imports", [])),
                json.dumps(entry.get("business_entities", [])),
                entry.get("scan_timestamp"),
            ),
        )

    connection.execute(
        """
        INSERT INTO index_meta (id, source, file_count, last_scan)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source = excluded.source,
            file_count = excluded.file_count,
            last_scan = excluded.last_scan
        """,
        (source, len(entries), datetime.now(timezone.utc).isoformat()),
    )
    connection.commit()
    connection.close()
