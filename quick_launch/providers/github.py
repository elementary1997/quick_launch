import os
from pathlib import Path

from .base import CloneResult, Provider


class GitHubProvider(Provider):
    name = "GitHub"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "github.com" in url

    def check_access(self, keys_dir: Path) -> CloneResult:
        token = (
            os.environ.get("GITHUB_TOKEN")
            or _read_token_file(keys_dir / "github.token")
        )
        if token:
            clone_url = _inject_token(self.url, token)
            display = _strip_token(clone_url)
            return CloneResult(url=clone_url, display_url=display)
        # fall back to SSH if key exists
        key = keys_dir / "github_rsa"
        if key.exists():
            return CloneResult(url=_to_ssh(self.url), display_url=_to_ssh(self.url))
        # public / no auth
        return CloneResult(url=self.url, display_url=self.url)

    def credential_hint(self) -> str:
        return (
            "GitHub: set GITHUB_TOKEN env var, or place a personal access token in\n"
            "  keys/github.token, or add an SSH key at keys/github_rsa"
        )


def _inject_token(url: str, token: str) -> str:
    if url.startswith("https://"):
        return url.replace("https://", f"https://{token}@", 1)
    return url


def _strip_token(url: str) -> str:
    import re
    return re.sub(r"https://[^@]+@", "https://***@", url)


def _to_ssh(url: str) -> str:
    # https://github.com/user/repo  ->  git@github.com:user/repo.git
    url = url.rstrip("/").removesuffix(".git")
    parts = url.replace("https://github.com/", "").split("/")
    return f"git@github.com:{'/'.join(parts)}.git"


def _read_token_file(path: Path) -> str:
    if path.exists():
        return path.read_text().strip()
    return ""
