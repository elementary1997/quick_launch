import os
import re
from pathlib import Path

from .base import CloneResult, Provider, parse_tree_url


class GitLabProvider(Provider):
    name = "GitLab"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "gitlab.com" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        repo_url, branch, subdir = parse_tree_url(self.url, "gitlab.com")
        ssh_url = _to_ssh(repo_url)

        key = self._find_ssh_key(keys_dir, "gitlab")
        if key:
            return CloneResult(
                url=ssh_url, display_url=ssh_url,
                has_auth=True, ssh_key=key, branch=branch, subdir=subdir,
            )
        token = os.environ.get("GITLAB_TOKEN") or _read_file(keys_dir / "gitlab.token")
        if token:
            clone_url = repo_url.replace("https://", f"https://oauth2:{token}@", 1)
            return CloneResult(
                url=clone_url, display_url=_mask(clone_url),
                has_auth=True, branch=branch, subdir=subdir,
            )
        return CloneResult(url=repo_url, display_url=repo_url, branch=branch, subdir=subdir)

    def credential_hint(self) -> str:
        return (
            "GitLab: SSH key at keys/gitlab_ed25519 or keys/gitlab_rsa (or ~/.ssh/id_*),\n"
            "  or GITLAB_TOKEN env var / keys/gitlab.token"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://gitlab.com/", "").split("/")
    return f"git@gitlab.com:{'/'.join(parts)}.git"


def _mask(url: str) -> str:
    return re.sub(r"https://[^@]+@", "https://***@", url)


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
