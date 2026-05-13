import os
from pathlib import Path

from .base import CloneResult, Provider


class BitbucketProvider(Provider):
    name = "Bitbucket"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "bitbucket.org" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        key = self._find_ssh_key(keys_dir, "bitbucket")
        if key:
            return CloneResult(
                url=_to_ssh(self.url),
                display_url=_to_ssh(self.url),
                has_auth=True,
                ssh_key=key,
            )
        user = os.environ.get("BITBUCKET_USER") or _read_file(keys_dir / "bitbucket.user")
        password = os.environ.get("BITBUCKET_APP_PASSWORD") or _read_file(keys_dir / "bitbucket.token")
        if user and password:
            clone_url = self.url.replace("https://", f"https://{user}:{password}@", 1)
            return CloneResult(url=clone_url, display_url=self.url, has_auth=True)
        return CloneResult(url=self.url, display_url=self.url, has_auth=False)

    def credential_hint(self) -> str:
        return (
            "Bitbucket: SSH key at keys/bitbucket_ed25519 or keys/bitbucket_rsa (or ~/.ssh/id_*),\n"
            "  or BITBUCKET_USER + BITBUCKET_APP_PASSWORD env vars / keys/bitbucket.{user,token}"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://bitbucket.org/", "").split("/")
    return f"git@bitbucket.org:{'/'.join(parts)}.git"


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
