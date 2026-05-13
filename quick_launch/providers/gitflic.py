import os
from pathlib import Path

from .base import CloneResult, Provider


class GitFlicProvider(Provider):
    name = "GitFlic"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "gitflic.ru" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        token = os.environ.get("GITFLIC_TOKEN") or _read_file(keys_dir / "gitflic.token")
        if token:
            clone_url = self.url.replace("https://", f"https://oauth2:{token}@", 1)
            return CloneResult(url=clone_url, display_url=self.url)

        key = keys_dir / "gitflic_rsa"
        if key.exists():
            return CloneResult(url=_to_ssh(self.url), display_url=_to_ssh(self.url))

        return CloneResult(url=self.url, display_url=self.url)

    def credential_hint(self) -> str:
        return (
            "GitFlic: set GITFLIC_TOKEN env var, or place token in keys/gitflic.token,\n"
            "  or add an SSH key at keys/gitflic_rsa"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://gitflic.ru/", "").split("/")
    return f"git@gitflic.ru:{'/'.join(parts)}.git"


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
