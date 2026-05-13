from pathlib import Path

import git
from rich.console import Console

console = Console()


def clone(clone_url: str, display_url: str, dest: Path) -> git.Repo:
    if dest.exists() and any(dest.iterdir()):
        console.print(f"[yellow]Directory {dest} exists, pulling latest changes...[/yellow]")
        repo = git.Repo(dest)
        repo.remotes.origin.pull()
        return repo

    console.print(f"[cyan]Cloning[/cyan] {display_url} → {dest}")
    repo = git.Repo.clone_from(clone_url, dest, progress=_Progress())
    console.print("[green]✓ Clone complete[/green]")
    return repo


class _Progress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        if message:
            console.print(f"  [dim]{message}[/dim]")
