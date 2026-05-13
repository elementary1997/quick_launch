import os
from pathlib import Path

from .base import CloneResult, Provider


class GitFlicProvider(Provider):
    name = "GitFlic"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "gitflic.ru" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        key = self._find_ssh_key(keys_dir, "gitflic")
        if key:
            return CloneResult(
                url=_to_ssh(self.url),
                display_url=_to_ssh(self.url),
                has_auth=True,
                ssh_key=key,
            )
        token = os.environ.get("GITFLIC_TOKEN") or _read_file(keys_dir / "gitflic.token")
        if token:
            clone_url = self.url.replace("https://", f"https://oauth2:{token}@", 1)
            return CloneResult(url=clone_url, display_url=self.url, has_auth=True)
        return CloneResult(url=self.url, display_url=self.url, has_auth=False)

    def credential_hint(self) -> str:
        return (
            "GitFlic: SSH key at keys/gitflic_ed25519 or keys/gitflic_rsa (or ~/.ssh/id_*),\n"
            "  or GITFLIC_TOKEN env var / keys/gitflic.token"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://gitflic.ru/", "").split("/")
    return f"git@gitflic.ru:{'/'.join(parts)}.git"


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
