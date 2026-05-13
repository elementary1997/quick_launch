import os
import re
from pathlib import Path

from .base import CloneResult, Provider


class GitHubProvider(Provider):
    name = "GitHub"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "github.com" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        key = self._find_ssh_key(keys_dir, "github")
        if key:
            return CloneResult(
                url=_to_ssh(self.url),
                display_url=_to_ssh(self.url),
                has_auth=True,
                ssh_key=key,
            )
        token = os.environ.get("GITHUB_TOKEN") or _read_file(keys_dir / "github.token")
        if token:
            clone_url = self.url.replace("https://", f"https://{token}@", 1)
            return CloneResult(url=clone_url, display_url=_mask(clone_url), has_auth=True)
        return CloneResult(url=self.url, display_url=self.url, has_auth=False)

    def credential_hint(self) -> str:
        return (
            "GitHub: SSH key at keys/github_ed25519 or keys/github_rsa (or ~/.ssh/id_*),\n"
            "  or GITHUB_TOKEN env var / keys/github.token"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://github.com/", "").split("/")
    return f"git@github.com:{'/'.join(parts)}.git"


def _mask(url: str) -> str:
    return re.sub(r"https://[^@]+@", "https://***@", url)


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
