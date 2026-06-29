from pathlib import Path
from typing import Any

import yaml

from app.config import settings


def load_domain_pack(domain_name: str) -> dict[str, Any]:
    pack_path = settings.domain_packs_dir / f"{domain_name}.yaml"
    if not pack_path.exists():
        raise FileNotFoundError(f"Domain pack not found: {domain_name}")
    with pack_path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_all_domain_packs() -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    if not settings.domain_packs_dir.exists():
        return packs
    for pack_file in settings.domain_packs_dir.glob("*.yaml"):
        with pack_file.open(encoding="utf-8") as file:
            data = yaml.safe_load(file)
            domain = data.get("domain_name", pack_file.stem)
            packs[domain] = data
    return packs


def list_domain_pack_names() -> list[str]:
    if not settings.domain_packs_dir.exists():
        return []
    return sorted(path.stem for path in settings.domain_packs_dir.glob("*.yaml"))
