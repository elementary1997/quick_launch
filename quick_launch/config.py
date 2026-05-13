"""
Central path configuration. Reads overrides from QL_KEYS_DIR / QL_SANDBOXES_DIR env vars.
"""
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent

KEYS_DIR: Path = Path(os.environ.get("QL_KEYS_DIR", _ROOT / "keys"))
SANDBOXES_DIR: Path = Path(os.environ.get("QL_SANDBOXES_DIR", _ROOT / "sandboxes"))
