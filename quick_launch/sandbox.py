"""Docker Compose sandbox management."""
import json
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quick_launch import port_manager

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
        console.print("[yellow]  No docker-compose file found — skipping[/yellow]")
        return False

    console.print(f"  compose  : [cyan]{compose_file.name}[/cyan]")
    _check_docker()

    # Check and remap conflicting ports before starting
    port_manager.ensure_ports_free(compose_file, repo_dir)

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
    if detach:
        cmd.append("-d")

    console.print(f"  command  : [dim]{' '.join(cmd)}[/dim]")
    rc = _stream(cmd, cwd=repo_dir)

    if rc != 0:
        console.print("[red]  ✗ docker compose up failed[/red]")
        return False

    if detach:
        _verify_containers(repo_dir, compose_file)

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
    """Parse compose YAML to predict URLs from declared port mappings."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []
    ports = port_manager.get_effective_ports(compose_file, repo_dir)
    return _ports_to_urls(ports)


def get_web_urls(repo_dir: Path) -> list[str]:
    """Read actual port bindings from running containers."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []

    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []

    host_ports: list[tuple[str, int, int]] = []
    for line in result.stdout.strip().splitlines():
        try:
            svc = json.loads(line)
            svc_name = svc.get("Service", "")
            for pub in svc.get("Publishers", []):
                h = pub.get("PublishedPort", 0)
                c = pub.get("TargetPort", 0)
                if h:
                    host_ports.append((svc_name, h, c))
        except (json.JSONDecodeError, KeyError):
            pass

    return _ports_to_urls(host_ports)


# ── internals ────────────────────────────────────────────────────────────────

def _ports_to_urls(ports: list[tuple[str, int, int]]) -> list[str]:
    urls: set[str] = set()
    for _, host_port, _ in ports:
        proto = "https" if host_port in (443, 8443) else "http"
        urls.add(f"{proto}://localhost:{host_port}")
    return sorted(urls)


def _verify_containers(repo_dir: Path, compose_file: Path) -> None:
    """Check container states and show a status table after detached start."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        _print_status(repo_dir, compose_file)
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Service", style="cyan")
    table.add_column("State")
    table.add_column("Ports", style="dim")

    any_unhealthy = False
    for line in result.stdout.strip().splitlines():
        try:
            svc = json.loads(line)
            name = svc.get("Service", svc.get("Name", "?"))
            state = svc.get("State", "?")
            health = svc.get("Health", "")
            publishers = svc.get("Publishers") or []

            port_strs = []
            for p in publishers:
                h = p.get("PublishedPort", 0)
                c = p.get("TargetPort", 0)
                if h:
                    port_strs.append(f"{h}→{c}")

            if state == "running":
                state_str = "[green]running[/green]"
                if health == "healthy":
                    state_str += " [green](healthy)[/green]"
                elif health == "unhealthy":
                    state_str += " [red](unhealthy)[/red]"
                    any_unhealthy = True
            else:
                state_str = f"[red]{state}[/red]"
                any_unhealthy = True

            table.add_row(name, state_str, "  ".join(port_strs))
        except (json.JSONDecodeError, KeyError):
            pass

    console.print(table)

    if any_unhealthy:
        console.print(
            "  [yellow]⚠ Some containers are not healthy.[/yellow] "
            "Check logs: [dim]docker compose logs -f[/dim]"
        )


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


def _stream(cmd: list[str], cwd: Path) -> int:
    with subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    ) as proc:
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.rstrip()
            if not line:
                continue
            low = line.lower()
            if any(w in low for w in ("error", "failed", "fatal")):
                console.print(f"  [red]{line}[/red]")
            elif any(w in low for w in ("warning", "warn")):
                console.print(f"  [yellow]{line}[/yellow]")
            elif any(w in low for w in ("started", "created", "pulled", "built", "running", "healthy")):
                console.print(f"  [green]{line}[/green]")
            else:
                console.print(f"  [dim]{line}[/dim]")
        proc.wait()
        return proc.returncode


def _check_docker() -> None:
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]  Docker is not running. Start Docker first.[/red]")
        raise SystemExit(1)
