"""
ql — Quick Launch CLI
Usage:
    ql launch <repo-url>       Clone, configure env, and spin up docker-compose
    ql down <repo-url|name>    Stop the sandbox
    ql status <repo-url|name>  Show sandbox container status
    ql keys                    Show credential status for all providers
"""
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from quick_launch import __version__
from quick_launch import providers
from quick_launch import cloner, env_manager, readme, sandbox

app = typer.Typer(help="Quickly clone and sandbox any git project.", no_args_is_help=True)
console = Console()

KEYS_DIR = Path(__file__).parent.parent / "keys"
SANDBOXES_DIR = Path(__file__).parent.parent / "sandboxes"


def _repo_name(url: str) -> str:
    return url.rstrip("/").rstrip(".git").split("/")[-1]


def _sandbox_path(url: str) -> Path:
    return SANDBOXES_DIR / _repo_name(url)


@app.command()
def launch(
    url: Annotated[str, typer.Argument(help="Repository URL (GitHub / Bitbucket / GitFlic)")],
    no_sandbox: Annotated[bool, typer.Option("--no-sandbox", help="Skip docker-compose")] = False,
    no_readme: Annotated[bool, typer.Option("--no-readme", help="Skip README display")] = False,
    foreground: Annotated[bool, typer.Option("--fg", help="Run docker-compose in foreground")] = False,
) -> None:
    """Clone a repo, configure .env, and start the Docker sandbox."""
    console.print(Rule(f"[bold blue]quick-launch v{__version__}[/bold blue]"))

    # 1. Detect provider & check credentials
    console.print(Rule("1 / Access check"))
    try:
        provider = providers.detect(url)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    KEYS_DIR.mkdir(exist_ok=True)
    clone_result = provider.check_access(KEYS_DIR)
    console.print(
        Panel(
            f"Provider : [bold]{provider.name}[/bold]\n"
            f"Clone URL: {clone_result.display_url}\n"
            f"Auth     : {'[green]token/key[/green]' if clone_result.url != url else '[yellow]none (public?)[/yellow]'}",
            border_style="cyan",
        )
    )

    # 2. Clone
    console.print(Rule("2 / Clone"))
    SANDBOXES_DIR.mkdir(exist_ok=True)
    dest = _sandbox_path(url)
    try:
        cloner.clone(clone_result.url, clone_result.display_url, dest)
    except Exception as e:
        console.print(f"[red]Clone failed: {e}[/red]")
        console.print(f"\n[dim]{provider.credential_hint()}[/dim]")
        raise typer.Exit(1)

    # 3. README
    if not no_readme:
        console.print(Rule("3 / README"))
        readme.display(dest)

    # 4. .env setup
    console.print(Rule("4 / Environment"))
    env_manager.prepare(dest)

    # 5. Sandbox
    if no_sandbox:
        console.print("[dim]Skipping sandbox (--no-sandbox)[/dim]")
    else:
        console.print(Rule("5 / Sandbox"))
        sandbox.up(dest, detach=not foreground)

    console.print(Rule("[bold green]Done[/bold green]"))


@app.command()
def down(
    url_or_name: Annotated[str, typer.Argument(help="Repo URL or sandbox name")],
) -> None:
    """Stop a running sandbox."""
    dest = _resolve_path(url_or_name)
    sandbox.down(dest)


@app.command()
def status(
    url_or_name: Annotated[str, typer.Argument(help="Repo URL or sandbox name")],
) -> None:
    """Show container status for a sandbox."""
    dest = _resolve_path(url_or_name)
    sandbox.status(dest)


@app.command()
def keys() -> None:
    """Show credential status for all supported providers."""
    KEYS_DIR.mkdir(exist_ok=True)
    table_data = []
    for cls in providers.PROVIDERS:
        inst = cls.__new__(cls)
        inst.url = ""
        hint = inst.credential_hint()
        table_data.append((cls.name, hint))

    from rich.table import Table
    t = Table(title="Credential hints", show_lines=True)
    t.add_column("Provider", style="cyan")
    t.add_column("How to configure")
    for name, hint in table_data:
        t.add_row(name, hint)
    console.print(t)


def _resolve_path(url_or_name: str) -> Path:
    if "/" in url_or_name and "://" in url_or_name:
        return _sandbox_path(url_or_name)
    return SANDBOXES_DIR / url_or_name


if __name__ == "__main__":
    app()
