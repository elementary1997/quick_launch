from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CloneResult:
    url: str           # final URL used for cloning (with credentials injected)
    display_url: str   # URL safe to print (no secrets)
    has_auth: bool = False  # True when a real credential was found/injected


class Provider(ABC):
    name: str = "generic"

    def __init__(self, url: str) -> None:
        self.url = url

    @classmethod
    @abstractmethod
    def matches(cls, url: str) -> bool: ...

    @abstractmethod
    def check_access(self, keys_dir: Path) -> CloneResult:
        """Verify credentials exist and return clone-ready URL."""
        ...

    @abstractmethod
    def credential_hint(self) -> str:
        """Human-readable hint on how to create credentials for this provider."""
        ...
