"""
ql — Quick Launch CLI
Commands: launch, down, status, list, keys
"""
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Generator

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

_TOTAL_STEPS = 5

_PROVIDER_KEY_FILE: dict[str, str] = {
    "GitHub": "github_ed25519",
    "GitLab": "gitlab_ed25519",
    "GitFlic": "gitflic_ed25519",
    "Bitbucket": "bitbucket_ed25519",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _repo_name(url: str) -> str:
    clean = re.sub(r"/tree/.*$", "", url.rstrip("/"))
    return clean.removesuffix(".git").split("/")[-1]


def _sandbox_path(url: str) -> Path:
    return config.SANDBOXES_DIR / _repo_name(url)


def _work_dir(clone_dest: Path, subdir: str | None) -> Path:
    return clone_dest / subdir if subdir else clone_dest


def _resolve_path(url_or_name: str) -> Path:
    if "://" in url_or_name:
        from quick_launch.providers.base import parse_tree_url
        host_m = re.search(r"://([^/]+)", url_or_name)
        h = host_m.group(1) if host_m else ""
        repo_url, _, subdir = parse_tree_url(url_or_name, h)
        base = config.SANDBOXES_DIR / _repo_name(repo_url)
        return base / subdir if subdir else base
    return config.SANDBOXES_DIR / url_or_name


@contextmanager
def _step(n: int, name: str) -> Generator[None, None, None]:
    """Print a step header, measure time, print result on exit."""
    console.print(f"\n[bold cyan]┌─ {n}/{_TOTAL_STEPS}  {name}[/bold cyan]")
    t0 = time.perf_counter()
    try:
        yield
        elapsed = time.perf_counter() - t0
        console.print(f"[bold cyan]└─[/bold cyan] [green]✓ done[/green]  [dim]{elapsed:.1f}s[/dim]")
    except (SystemExit, typer.Exit):
        elapsed = time.perf_counter() - t0
        console.print(f"[bold cyan]└─[/bold cyan] [red]✗ failed[/red]  [dim]{elapsed:.1f}s[/dim]")
        raise


def _print_summary(work_dir: Path, env_path: Path | None) -> None:
    """Final panel: web URLs + auth credentials."""
    lines: list[str] = []

    # --- web URLs (running containers first, then from YAML if not started)
    web_urls = sandbox.get_web_urls(work_dir)
    if not web_urls:
        web_urls = sandbox.predict_urls(work_dir)
        url_source = "predicted from compose"
    else:
        url_source = "live"

    if web_urls:
        lines.append(f"[bold]Web interfaces[/bold] [dim]({url_source})[/dim]")
        for u in web_urls:
            lines.append(f"  [link={u}][cyan]{u}[/cyan][/link]")

    # --- auth vars from .env
    if env_path and env_path.exists():
        auth = env_manager.get_auth_vars(env_path)
        if auth:
            if lines:
                lines.append("")
            lines.append("[bold]Auth credentials  [dim](.env)[/dim][/bold]")
            for k, v in sorted(auth.items()):
                val_str = f"[yellow]{v}[/yellow]" if v else "[red]<empty>[/red]"
                lines.append(f"  [cyan]{k}[/cyan] = {val_str}")

    if lines:
        console.print(Panel(
            "\n".join(lines),
            title="[bold green]Summary[/bold green]",
            border_style="green",
        ))


# ── commands ─────────────────────────────────────────────────────────────────

@app.command()
def launch(
    url: Annotated[str, typer.Argument(help="Repo URL — GitHub / GitLab / Bitbucket / GitFlic")],
    no_sandbox: Annotated[bool, typer.Option("--no-sandbox", help="Skip docker-compose")] = False,
    no_readme: Annotated[bool, typer.Option("--no-readme", help="Skip README")] = False,
    foreground: Annotated[bool, typer.Option("--fg", help="Attach to compose output")] = False,
) -> None:
    """Clone a repo, configure .env, and start the Docker sandbox."""
    console.print(Rule(f"[bold blue]quick-launch v{__version__}[/bold blue]"))

    env_path: Path | None = None

    # 1 ── access check ────────────────────────────────────────────────────────
    with _step(1, "Access check"):
        try:
            provider = providers.detect(url)
        except ValueError as e:
            console.print(f"  [red]{e}[/red]")
            raise typer.Exit(1)

        config.KEYS_DIR.mkdir(exist_ok=True)
        clone_result = provider.check_access(config.KEYS_DIR)

        if not clone_result.has_auth:
            dest_key = _PROVIDER_KEY_FILE.get(provider.name)
            if dest_key:
                key = credentials.ask_for_ssh_key(provider.name, config.KEYS_DIR, dest_key)
                if key:
                    clone_result = provider.check_access(config.KEYS_DIR)

        if clone_result.ssh_key:
            auth_str = f"[green]SSH[/green]  [dim]{clone_result.ssh_key}[/dim]"
        elif clone_result.has_auth:
            auth_str = "[green]token[/green]"
        else:
            auth_str = "[yellow]none — public repo[/yellow]"

        info = [
            f"  provider : [bold]{provider.name}[/bold]",
            f"  url      : {clone_result.display_url}",
            f"  auth     : {auth_str}",
        ]
        if clone_result.branch:
            info.append(f"  branch   : [cyan]{clone_result.branch}[/cyan]")
        if clone_result.subdir:
            info.append(f"  subdir   : [cyan]{clone_result.subdir}[/cyan]")
        for line in info:
            console.print(line)

    # 2 ── clone ───────────────────────────────────────────────────────────────
    with _step(2, "Clone"):
        config.SANDBOXES_DIR.mkdir(exist_ok=True)
        clone_dest = _sandbox_path(url)
        work = _work_dir(clone_dest, clone_result.subdir)
        try:
            cloner.clone(
                clone_result.url,
                clone_result.display_url,
                clone_dest,
                ssh_key=clone_result.ssh_key,
                branch=clone_result.branch,
            )
        except Exception as e:
            console.print(f"  [red]clone failed:[/red] {e}")
            console.print(f"  [dim]{provider.credential_hint()}[/dim]")
            raise typer.Exit(1)

        if clone_result.subdir:
            if not work.exists():
                console.print(f"  [red]subdir not found in repo:[/red] {clone_result.subdir}")
                raise typer.Exit(1)
            console.print(f"  work dir : [dim]{work}[/dim]")

    # 3 ── readme ──────────────────────────────────────────────────────────────
    if not no_readme:
        with _step(3, "README"):
            readme.display(work)
    else:
        console.print(f"\n[dim]─ 3/{_TOTAL_STEPS} README skipped[/dim]")

    # 4 ── environment ─────────────────────────────────────────────────────────
    with _step(4, "Environment"):
        env_path = env_manager.prepare(work)

    # 5 ── sandbox ─────────────────────────────────────────────────────────────
    if no_sandbox:
        console.print(f"\n[dim]─ 5/{_TOTAL_STEPS} Sandbox skipped (--no-sandbox)[/dim]")
    else:
        with _step(5, "Sandbox"):
            sandbox.up(work, detach=not foreground)

    # ── summary ───────────────────────────────────────────────────────────────
    console.print()
    _print_summary(work, env_path)
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
    """List all local sandboxes."""
    config.SANDBOXES_DIR.mkdir(exist_ok=True)
    entries = sorted(
        (s for s in config.SANDBOXES_DIR.iterdir() if s.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not entries:
        console.print("[dim]No sandboxes yet. Run: ql launch <repo-url>[/dim]")
        return

    table = Table(title="Local sandboxes", header_style="bold magenta", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Compose file")
    table.add_column("Predicted URLs", style="dim")
    table.add_column("Path", style="dim")

    for s in entries:
        compose = sandbox.find_compose(s)
        urls = ", ".join(sandbox.predict_urls(s)) if compose else ""
        table.add_row(s.name, compose.name if compose else "—", urls, str(s))

    console.print(table)


@app.command()
def keys() -> None:
    """Show credential configuration hints for all providers."""
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
