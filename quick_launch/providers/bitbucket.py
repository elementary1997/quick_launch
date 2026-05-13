import os
from pathlib import Path

from .base import CloneResult, Provider, parse_tree_url


class BitbucketProvider(Provider):
    name = "Bitbucket"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "bitbucket.org" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        repo_url, branch, subdir = parse_tree_url(self.url, "bitbucket.org")
        ssh_url = _to_ssh(repo_url)

        key = self._find_ssh_key(keys_dir, "bitbucket")
        if key:
            return CloneResult(
                url=ssh_url, display_url=ssh_url,
                has_auth=True, ssh_key=key, branch=branch, subdir=subdir,
            )
        user = os.environ.get("BITBUCKET_USER") or _read_file(keys_dir / "bitbucket.user")
        password = os.environ.get("BITBUCKET_APP_PASSWORD") or _read_file(keys_dir / "bitbucket.token")
        if user and password:
            clone_url = repo_url.replace("https://", f"https://{user}:{password}@", 1)
            return CloneResult(
                url=clone_url, display_url=repo_url,
                has_auth=True, branch=branch, subdir=subdir,
            )
        return CloneResult(url=repo_url, display_url=repo_url, branch=branch, subdir=subdir)

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
