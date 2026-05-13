from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

_SSH_KEY_NAMES = ["id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"]


@dataclass
class CloneResult:
    url: str                    # URL used for cloning
    display_url: str            # URL safe to print (no secrets)
    has_auth: bool = False      # True when a real credential was found
    ssh_key: Path | None = None # Path to private key when using SSH auth


class Provider(ABC):
    name: str = "generic"

    def __init__(self, url: str) -> None:
        self.url = url

    @classmethod
    @abstractmethod
    def matches(cls, url: str) -> bool: ...

    @abstractmethod
    def check_access(self, keys_dir: Path) -> CloneResult:
        """Find credentials and return clone-ready result. Never prints."""
        ...

    @abstractmethod
    def credential_hint(self) -> str:
        """Human-readable hint on how to obtain credentials for this provider."""
        ...

    def _find_ssh_key(self, keys_dir: Path, provider_prefix: str) -> Path | None:
        """
        Lookup order:
        1. keys/<prefix>_ed25519, keys/<prefix>_rsa  (provider-specific)
        2. keys/id_ed25519, keys/id_rsa              (generic in keys dir)
        3. ~/.ssh/id_ed25519, ~/.ssh/id_rsa           (system)
        """
        candidates = (
            [keys_dir / f"{provider_prefix}_{k.split('id_')[1]}" for k in _SSH_KEY_NAMES]
            + [keys_dir / k for k in _SSH_KEY_NAMES]
            + [Path.home() / ".ssh" / k for k in _SSH_KEY_NAMES]
        )
        for path in candidates:
            if path.exists() and not path.suffix == ".pub":
                return path
        return None
