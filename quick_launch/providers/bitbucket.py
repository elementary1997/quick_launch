import os
from pathlib import Path

from .base import CloneResult, Provider


class BitbucketProvider(Provider):
    name = "Bitbucket"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "bitbucket.org" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        user = os.environ.get("BITBUCKET_USER") or _read_file(keys_dir / "bitbucket.user")
        password = os.environ.get("BITBUCKET_APP_PASSWORD") or _read_file(keys_dir / "bitbucket.token")

        if user and password:
            clone_url = self.url.replace("https://", f"https://{user}:{password}@", 1)
            return CloneResult(url=clone_url, display_url=self.url, has_auth=True)

        key = keys_dir / "bitbucket_rsa"
        if key.exists():
            return CloneResult(url=_to_ssh(self.url), display_url=_to_ssh(self.url), has_auth=True)

        return CloneResult(url=self.url, display_url=self.url, has_auth=False)

    def credential_hint(self) -> str:
        return (
            "Bitbucket: set BITBUCKET_USER + BITBUCKET_APP_PASSWORD env vars, or\n"
            "  place them in keys/bitbucket.user and keys/bitbucket.token, or\n"
            "  add an SSH key at keys/bitbucket_rsa"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://bitbucket.org/", "").split("/")
    return f"git@bitbucket.org:{'/'.join(parts)}.git"


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
