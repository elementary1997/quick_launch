"""
ql — Quick Launch CLI
Usage:
    ql launch <repo-url>       Clone, configure env, and spin up docker-compose
    ql down <repo-url|name>    Stop the sandbox
    ql status <repo-url|name>  Show sandbox container status
    ql list                    List all local sandboxes
    ql keys                    Show credential status for all providers
"""
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from quick_launch import __version__
from quick_launch import config, providers
from quick_launch import cloner, credentials, env_manager, readme, sandbox

app = typer.Typer(help="Quickly clone and sandbox any git project.", no_args_is_help=True)
console = Console()

# Destination key filename per provider (used when copying a key interactively)
_PROVIDER_KEY_FILE: dict[str, str] = {
    "GitHub": "github_ed25519",
    "GitLab": "gitlab_ed25519",
    "GitFlic": "gitflic_ed25519",
    "Bitbucket": "bitbucket_ed25519",
}


def _repo_name(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").split("/")[-1]


def _sandbox_path(url: str) -> Path:
    return config.SANDBOXES_DIR / _repo_name(url)


def _resolve_path(url_or_name: str) -> Path:
    if "://" in url_or_name:
        return _sandbox_path(url_or_name)
    return config.SANDBOXES_DIR / url_or_name


@app.command()
def launch(
    url: Annotated[str, typer.Argument(help="Repository URL (GitHub / GitLab / Bitbucket / GitFlic)")],
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

    config.KEYS_DIR.mkdir(exist_ok=True)
    clone_result = provider.check_access(config.KEYS_DIR)

    # Interactive SSH key selection when no credentials were found
    if not clone_result.has_auth:
        dest_key_name = _PROVIDER_KEY_FILE.get(provider.name)
        if dest_key_name:
            key = credentials.ask_for_ssh_key(provider.name, config.KEYS_DIR, dest_key_name)
            if key:
                clone_result = provider.check_access(config.KEYS_DIR)

    if clone_result.ssh_key:
        auth_label = f"[green]SSH key[/green] [dim]({clone_result.ssh_key})[/dim]"
    elif clone_result.has_auth:
        auth_label = "[green]token[/green]"
    else:
        auth_label = "[yellow]none — public repo[/yellow]"
    console.print(
        Panel(
            f"Provider : [bold]{provider.name}[/bold]\n"
            f"Clone URL: {clone_result.display_url}\n"
            f"Auth     : {auth_label}",
            border_style="cyan",
        )
    )

    # 2. Clone
    console.print(Rule("2 / Clone"))
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    dest = _sandbox_path(url)
    try:
        cloner.clone(clone_result.url, clone_result.display_url, dest, ssh_key=clone_result.ssh_key)
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
    sandbox.down(_resolve_path(url_or_name))


@app.command()
def status(
    url_or_name: Annotated[str, typer.Argument(help="Repo URL or sandbox name")],
) -> None:
    """Show container status for a sandbox."""
    sandbox.status(_resolve_path(url_or_name))


@app.command(name="list")
def list_sandboxes() -> None:
    """List all local sandboxes with their compose status."""
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    sandboxes = sorted(config.SANDBOXES_DIR.iterdir()) if config.SANDBOXES_DIR.exists() else []

    if not sandboxes:
        console.print("[dim]No sandboxes yet. Run: ql launch <repo-url>[/dim]")
        return

    table = Table(title="Local sandboxes", show_lines=False, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Compose file")
    table.add_column("Path", style="dim")

    for s in sandboxes:
        if not s.is_dir():
            continue
        compose = sandbox.find_compose(s)
        table.add_row(
            s.name,
            compose.name if compose else "[dim]—[/dim]",
            str(s),
        )

    console.print(table)


@app.command()
def keys() -> None:
    """Show credential status for all supported providers."""
    config.KEYS_DIR.mkdir(exist_ok=True)

    table = Table(title="Credential hints", show_lines=True)
    table.add_column("Provider", style="cyan")
    table.add_column("How to configure")

    for cls in providers.PROVIDERS:
        inst = cls.__new__(cls)
        inst.url = ""
        table.add_row(cls.name, inst.credential_hint())

    console.print(table)


if __name__ == "__main__":
    app()
