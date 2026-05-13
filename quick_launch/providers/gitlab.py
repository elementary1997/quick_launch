import os
from pathlib import Path

from .base import CloneResult, Provider


class GitLabProvider(Provider):
    name = "GitLab"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "gitlab.com" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        token = os.environ.get("GITLAB_TOKEN") or _read_file(keys_dir / "gitlab.token")
        if token:
            clone_url = self.url.replace("https://", f"https://oauth2:{token}@", 1)
            return CloneResult(url=clone_url, display_url=self.url, has_auth=True)

        key = keys_dir / "gitlab_rsa"
        if key.exists():
            return CloneResult(url=_to_ssh(self.url), display_url=_to_ssh(self.url), has_auth=True)

        return CloneResult(url=self.url, display_url=self.url, has_auth=False)

    def credential_hint(self) -> str:
        return (
            "GitLab: set GITLAB_TOKEN env var, or place token in keys/gitlab.token,\n"
            "  or add an SSH key at keys/gitlab_rsa"
        )


def _to_ssh(url: str) -> str:
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://gitlab.com/", "").split("/")
    return f"git@gitlab.com:{'/'.join(parts)}.git"


def _read_file(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""
