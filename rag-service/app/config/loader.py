"""Config loader — reads JSON config files once at import time."""
import json
from pathlib import Path

_DIR = Path(__file__).parent / "json"

RETRIEVAL_CONFIG  = json.loads((_DIR / "retrieval_config.json").read_text())
INGESTION_CONFIG  = json.loads((_DIR / "ingestion_config.json").read_text())
