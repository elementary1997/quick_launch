from pathlib import Path

import git
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

console = Console()


def clone(
    clone_url: str,
    display_url: str,
    dest: Path,
    ssh_key: Path | None = None,
    branch: str | None = None,
) -> git.Repo:
    env = _ssh_env(ssh_key) if ssh_key and not _is_system_key(ssh_key) else None

    if dest.exists() and any(dest.iterdir()):
        console.print(f"  [yellow]already cloned[/yellow] — pulling latest changes")
        repo = git.Repo(dest)
        with repo.remotes.origin.config_writer as cw:
            cw.set("url", clone_url)
        repo.remotes.origin.pull(env=env)
        console.print("  [green]✓ pull complete[/green]")
        return repo

    console.print(f"  source : [cyan]{display_url}[/cyan]")
    console.print(f"  target : [cyan]{dest}[/cyan]")
    if ssh_key and not _is_system_key(ssh_key):
        console.print(f"  key    : [dim]{ssh_key}[/dim]")

    kwargs: dict = {"env": env, "progress": _make_progress()}
    if branch:
        kwargs["branch"] = branch

    repo = git.Repo.clone_from(clone_url, dest, **kwargs)
    console.print("  [green]✓ clone complete[/green]")
    return repo


def _is_system_key(key: Path) -> bool:
    try:
        return key.resolve().is_relative_to(Path.home() / ".ssh")
    except ValueError:
        return False


def _ssh_env(key: Path) -> dict[str, str]:
    return {"GIT_SSH_COMMAND": f"ssh -i {key} -o StrictHostKeyChecking=no"}


def _make_progress() -> "_RichProgress":
    bar = Progress(
        SpinnerColumn(),
        TextColumn("  [cyan]{task.description}[/cyan]"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    )
    bar.start()
    return _RichProgress(bar)


class _RichProgress(git.RemoteProgress):
    _OP_LABELS = {
        git.RemoteProgress.COUNTING: "Counting objects",
        git.RemoteProgress.COMPRESSING: "Compressing objects",
        git.RemoteProgress.WRITING: "Writing objects",
        git.RemoteProgress.RECEIVING: "Receiving objects",
        git.RemoteProgress.RESOLVING: "Resolving deltas",
        git.RemoteProgress.FINDING_SOURCES: "Finding sources",
        git.RemoteProgress.CHECKING_OUT: "Checking out files",
    }

    def __init__(self, bar: Progress) -> None:
        super().__init__()
        self._bar = bar
        self._tasks: dict[int, object] = {}

    def update(self, op_code: int, cur_count, max_count=None, message=""):  # type: ignore[override]  # noqa: ARG002
        base_op = op_code & ~(self.BEGIN | self.END)
        label = self._OP_LABELS.get(base_op, "Working")

        if op_code & self.BEGIN:
            total = int(max_count) if max_count else None
            task_id = self._bar.add_task(label, total=total)
            self._tasks[base_op] = task_id

        task_id = self._tasks.get(base_op)
        if task_id is not None and max_count:
            self._bar.update(task_id, completed=int(cur_count), total=int(max_count))

        if op_code & self.END:
            if task_id is not None:
                self._bar.update(task_id, completed=int(max_count or cur_count))
            self._bar.stop()
