"""
Docker Compose sandbox management.
"""
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

_COMPOSE_FILES = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]


def find_compose(repo_dir: Path) -> Path | None:
    for name in _COMPOSE_FILES:
        p = repo_dir / name
        if p.exists():
            return p
    return None


def up(repo_dir: Path, detach: bool = True) -> bool:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        console.print("[yellow]No docker-compose file found — skipping sandbox launch[/yellow]")
        return False

    console.print(f"[cyan]Found:[/cyan] {compose_file.name}")
    _check_docker()

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
    if detach:
        cmd.append("-d")

    console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=repo_dir)
    if result.returncode != 0:
        console.print("[red]✗ docker compose up failed[/red]")
        return False

    if detach:
        _print_status(repo_dir, compose_file)
    return True


def down(repo_dir: Path) -> None:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return
    subprocess.run(["docker", "compose", "-f", str(compose_file), "down"], cwd=repo_dir)
    console.print("[green]✓ Sandbox stopped[/green]")


def status(repo_dir: Path) -> None:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        console.print("[dim]No compose file[/dim]")
        return
    _print_status(repo_dir, compose_file)


def _print_status(repo_dir: Path, compose_file: Path) -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    console.print(Panel(result.stdout or "(no output)", title="[bold]Sandbox status[/bold]", border_style="green"))


def _check_docker() -> None:
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]Docker is not running. Please start Docker first.[/red]")
        raise SystemExit(1)
