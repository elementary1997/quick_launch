"""
Interactive startup TUI — shown when `ql` is run with no arguments.
"""
import subprocess
from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from quick_launch import __version__, config

console = Console()

_BANNER = """\
 ██████╗ ██╗
██╔═══██╗██║
██║   ██║██║
╚██╗  ██║██║
 ╚█████╔╝███████╗
  ╚════╝ ╚══════╝"""

_TAGLINE = "Clone · Configure · Sandbox"
_PROVIDERS = "GitHub  •  GitLab  •  Bitbucket  •  GitFlic"


def show_welcome() -> None:
    """Print the ASCII banner + quick stats."""
    banner = Text(_BANNER, style="bold cyan")
    meta = Text(f"\n{_TAGLINE}\n{_PROVIDERS}\nv{__version__}", style="dim")
    content = Align(Text.assemble(banner, meta), align="center")
    console.print(Panel(content, border_style="cyan", padding=(1, 4)))
    _print_stats()


def run() -> None:
    """Show welcome screen then enter the interactive command loop."""
    show_welcome()

    while True:
        _print_menu()
        choice = Prompt.ask(
            "\n[bold cyan]  ›[/bold cyan]",
            choices=["1", "2", "3", "4", "5", "q", ""],
            default="",
            show_choices=False,
            show_default=False,
        ).strip().lower()

        if choice in ("q", ""):
            break
        elif choice == "1":
            _cmd_launch()
        elif choice == "2":
            _cmd_list()
        elif choice == "3":
            _cmd_status()
        elif choice == "4":
            _cmd_keys()
        elif choice == "5":
            _cmd_down()

        console.print()


# ── menu sections ────────────────────────────────────────────────────────────

def _print_stats() -> None:
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    sandboxes = [s for s in config.SANDBOXES_DIR.iterdir() if s.is_dir()] if config.SANDBOXES_DIR.exists() else []

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=3,
        )
        running = len(result.stdout.strip().splitlines()) if result.returncode == 0 else "?"
    except Exception:
        running = "?"

    stats = Text()
    stats.append(f"  {len(sandboxes)} sandbox(es) locally", style="dim")
    stats.append("  •  ", style="dim")
    stats.append(f"{running} container(s) running", style="green" if running else "dim")
    console.print(stats)
    console.print()


def _print_menu() -> None:
    table = Table(box=None, show_header=False, padding=(0, 2), show_edge=False)
    table.add_column(style="bold cyan", width=5)
    table.add_column(style="bold", width=10)
    table.add_column(style="dim")

    rows = [
        ("1", "launch", "Clone a repo and start in Docker sandbox"),
        ("2", "list",   "Show all local sandboxes"),
        ("3", "status", "Docker container status for a sandbox"),
        ("4", "keys",   "Configure access credentials"),
        ("5", "down",   "Stop a running sandbox"),
        ("q", "quit",   ""),
    ]
    for key, cmd, desc in rows:
        table.add_row(f"[{key}]", cmd, desc)

    console.print(table)


# ── command handlers ─────────────────────────────────────────────────────────

def _cmd_launch() -> None:
    url = Prompt.ask("  [cyan]Repository URL[/cyan]").strip()
    if not url:
        return
    from quick_launch.cli import launch
    try:
        launch(url=url, no_sandbox=False, no_readme=False, foreground=False)
    except SystemExit:
        pass


def _cmd_list() -> None:
    from quick_launch.cli import list_sandboxes
    list_sandboxes()


def _cmd_status() -> None:
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    sandboxes = sorted(
        (s.name for s in config.SANDBOXES_DIR.iterdir() if s.is_dir()),
    ) if config.SANDBOXES_DIR.exists() else []

    if not sandboxes:
        console.print("[dim]  No sandboxes found.[/dim]")
        return

    for i, name in enumerate(sandboxes, 1):
        console.print(f"  [dim]{i}.[/dim] {name}")
    choice = Prompt.ask("  Sandbox name or number").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(sandboxes):
        choice = sandboxes[int(choice) - 1]
    from quick_launch.cli import status
    try:
        status(url_or_name=choice)
    except SystemExit:
        pass


def _cmd_keys() -> None:
    from quick_launch.cli import keys
    keys()


def _cmd_down() -> None:
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    sandboxes = sorted(
        (s.name for s in config.SANDBOXES_DIR.iterdir() if s.is_dir()),
    ) if config.SANDBOXES_DIR.exists() else []

    if not sandboxes:
        console.print("[dim]  No sandboxes found.[/dim]")
        return

    for i, name in enumerate(sandboxes, 1):
        console.print(f"  [dim]{i}.[/dim] {name}")
    choice = Prompt.ask("  Sandbox name or number").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(sandboxes):
        choice = sandboxes[int(choice) - 1]
    from quick_launch.cli import down
    try:
        down(url_or_name=choice)
    except SystemExit:
        pass
