import os
from pathlib import Path

from .base import CloneResult, Provider, parse_tree_url


class GitFlicProvider(Provider):
    name = "GitFlic"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "gitflic.ru" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        repo_url, branch, subdir = parse_tree_url(self.url, "gitflic.ru")
        ssh_url = _to_ssh(repo_url)

        key = self._find_ssh_key(keys_dir, "gitflic")
        if key:
            return CloneResult(
                url=ssh_url, display_url=ssh_url,
                has_auth=True, ssh_key=key, branch=branch, subdir=subdir,
            )
        token = os.environ.get("GITFLIC_TOKEN") or _read_file(keys_dir / "gitflic.token")
        if token:
            clone_url = repo_url.replace("https://", f"https://oauth2:{token}@", 1)
            return CloneResult(
                url=clone_url, display_url=repo_url,
                has_auth=True, branch=branch, subdir=subdir,
            )
        return CloneResult(url=repo_url, display_url=repo_url, branch=branch, subdir=subdir)

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
