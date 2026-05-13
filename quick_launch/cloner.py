from pathlib import Path

import git
from rich.console import Console

console = Console()


def clone(
    clone_url: str,
    display_url: str,
    dest: Path,
    ssh_key: Path | None = None,
    branch: str | None = None,
) -> git.Repo:
    # Use custom GIT_SSH_COMMAND only for keys in our own keys/ directory.
    # For ~/.ssh/ keys the system SSH agent already handles everything.
    env = _ssh_env(ssh_key) if ssh_key and not _is_system_key(ssh_key) else None

    if dest.exists() and any(dest.iterdir()):
        console.print("[yellow]Already cloned — pulling latest changes...[/yellow]")
        repo = git.Repo(dest)
        with repo.remotes.origin.config_writer as cw:
            cw.set("url", clone_url)
        repo.remotes.origin.pull(env=env)
        return repo

    console.print(f"[cyan]Cloning[/cyan] {display_url} → {dest}")
    if ssh_key and not _is_system_key(ssh_key):
        console.print(f"[dim]SSH key: {ssh_key}[/dim]")

    kwargs: dict = {"env": env, "progress": _Progress()}
    if branch:
        kwargs["branch"] = branch

    repo = git.Repo.clone_from(clone_url, dest, **kwargs)
    console.print("[green]✓ Clone complete[/green]")
    return repo


def _is_system_key(key: Path) -> bool:
    """True when the key lives in ~/.ssh/ — system agent handles auth, no override needed."""
    try:
        return key.resolve().is_relative_to(Path.home() / ".ssh")
    except ValueError:
        return False


def _ssh_env(key: Path) -> dict[str, str]:
    return {
        "GIT_SSH_COMMAND": f"ssh -i {key} -o StrictHostKeyChecking=no"
    }


class _Progress(git.RemoteProgress):
    def update(self, *args, message="", **_):  # type: ignore[override]
        if not message and len(args) > 3:
            message = args[3]
        if message:
            console.print(f"  [dim]{message}[/dim]")
