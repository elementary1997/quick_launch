"""Docker Compose sandbox management."""
import json
import subprocess
from pathlib import Path

import yaml
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

    console.print(f"  compose file : [cyan]{compose_file.name}[/cyan]")
    _check_docker()

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
    if detach:
        cmd.append("-d")

    console.print(f"  running      : [dim]{' '.join(cmd)}[/dim]")
    _stream(cmd, cwd=repo_dir)

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


def predict_urls(repo_dir: Path) -> list[str]:
    """Parse compose YAML to predict which ports will be exposed."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []
    try:
        data = yaml.safe_load(compose_file.read_text())
    except Exception:
        return []

    urls: list[str] = []
    for svc in (data or {}).get("services", {}).values():
        for port_entry in svc.get("ports", []):
            host_port = _parse_host_port(port_entry)
            if host_port:
                proto = "https" if host_port in (443, 8443) else "http"
                urls.append(f"{proto}://localhost:{host_port}")
    return sorted(set(urls))


def get_web_urls(repo_dir: Path) -> list[str]:
    """Read actual port bindings from running containers via docker compose ps."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []

    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []

    urls: list[str] = []
    for line in result.stdout.strip().splitlines():
        try:
            svc = json.loads(line)
            for pub in svc.get("Publishers", []):
                host_port = pub.get("PublishedPort", 0)
                if host_port:
                    proto = "https" if host_port in (443, 8443) else "http"
                    urls.append(f"{proto}://localhost:{host_port}")
        except (json.JSONDecodeError, KeyError):
            pass

    return sorted(set(urls))


def _parse_host_port(entry) -> int | None:
    """Extract host port from a compose ports entry (str or dict)."""
    if isinstance(entry, int):
        return entry
    if isinstance(entry, str):
        # "8080:80", "127.0.0.1:8080:80", "8080"
        parts = entry.split(":")
        try:
            return int(parts[-2]) if len(parts) >= 2 else int(parts[0])
        except (ValueError, IndexError):
            return None
    if isinstance(entry, dict):
        return entry.get("published") or entry.get("target")
    return None


def _stream(cmd: list[str], cwd: Path) -> int:
    """Run command and stream output, highlighting important lines."""
    with subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    ) as proc:
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.rstrip()
            if not line:
                continue
            if any(w in line.lower() for w in ("error", "failed", "fatal")):
                console.print(f"  [red]{line}[/red]")
            elif any(w in line.lower() for w in ("warning", "warn")):
                console.print(f"  [yellow]{line}[/yellow]")
            elif any(w in line.lower() for w in ("started", "created", "pulled", "built", "running")):
                console.print(f"  [green]{line}[/green]")
            else:
                console.print(f"  [dim]{line}[/dim]")
        proc.wait()
        if proc.returncode != 0:
            console.print(f"[red]✗ command exited with code {proc.returncode}[/red]")
        return proc.returncode


def _print_status(repo_dir: Path, compose_file: Path) -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if result.stdout.strip():
        console.print(Panel(
            result.stdout.strip(),
            title="[bold]Container status[/bold]",
            border_style="green",
        ))


def _check_docker() -> None:
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]Docker is not running. Please start Docker first.[/red]")
        raise SystemExit(1)
