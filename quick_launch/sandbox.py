"""Docker Compose sandbox management."""
import json
import subprocess
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from quick_launch import port_manager

console = Console()

_COMPOSE_FILES = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
_SKIP_DIRS = {"node_modules", "vendor", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def find_compose(repo_dir: Path) -> Path | None:
    """
    Find compose file: check repo_dir first, then recurse up to 3 levels deep.
    Skips common non-project directories (node_modules, .git, etc.).
    """
    # Direct check first (fastest path)
    for name in _COMPOSE_FILES:
        p = repo_dir / name
        if p.exists():
            return p

    # Recursive search — breadth-first so closest file wins
    queue: list[tuple[Path, int]] = [(repo_dir, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth >= 3:
            continue
        try:
            children = sorted(current.iterdir())
        except PermissionError:
            continue
        for child in children:
            if not child.is_dir() or child.name in _SKIP_DIRS:
                continue
            for name in _COMPOSE_FILES:
                p = child / name
                if p.exists():
                    return p
            queue.append((child, depth + 1))

    return None


def up(repo_dir: Path, detach: bool = True) -> bool:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        console.print("[yellow]  No compose file found — skipping sandbox[/yellow]")
        return False

    # compose_file may be in a subdir — run everything relative to its parent
    compose_dir = compose_file.parent
    console.print(f"  compose  : [cyan]{compose_file.relative_to(repo_dir)}[/cyan]")
    _check_docker()

    port_manager.ensure_ports_free(compose_file, compose_dir)

    cmd = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
    if detach:
        cmd.append("-d")

    console.print(f"  command  : [dim]{' '.join(cmd)}[/dim]")
    rc = _stream(cmd, cwd=compose_dir)

    if rc != 0:
        console.print("[red]  ✗ docker compose up failed[/red]")
        return False

    if detach:
        _wait_for_healthy(compose_dir, compose_file)

    return True


def down(repo_dir: Path) -> None:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        console.print(f"[yellow]No compose file found under {repo_dir.name}[/yellow]")
        return
    subprocess.run(["docker", "compose", "-f", str(compose_file), "down"], cwd=compose_file.parent)
    console.print("[green]✓ Sandbox stopped[/green]")


def status(repo_dir: Path) -> None:
    compose_file = find_compose(repo_dir)
    if not compose_file:
        console.print(f"[dim]No compose file found under {repo_dir.name}[/dim]")
        return
    _print_status(compose_file.parent, compose_file)


def predict_urls(repo_dir: Path) -> list[str]:
    """Parse compose YAML to predict URLs from declared port mappings."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []
    ports = port_manager.get_effective_ports(compose_file, compose_file.parent)
    return _ports_to_urls(ports)


def get_web_urls(repo_dir: Path) -> list[str]:
    """Read actual port bindings from running containers."""
    compose_file = find_compose(repo_dir)
    if not compose_file:
        return []

    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=compose_file.parent, capture_output=True, text=True,
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


def _wait_for_healthy(compose_dir: Path, compose_file: Path, timeout: int = 60) -> None:
    """
    Poll container states after detached start.
    Shows a live spinner and exits early once all containers are running.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("  [cyan]{task.description}[/cyan]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as bar:
        task = bar.add_task("Waiting for containers to start…", total=None)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            states = _get_states(compose_dir, compose_file)
            if not states:
                time.sleep(2)
                continue

            running = sum(1 for s in states.values() if s == "running")
            total = len(states)
            bar.update(task, description=f"Starting containers… {running}/{total} running")

            if all(s == "running" for s in states.values()):
                break
            if any(s in ("exited", "dead") for s in states.values()):
                break
            time.sleep(2)

    _verify_containers(compose_dir, compose_file)


def _get_states(compose_dir: Path, compose_file: Path) -> dict[str, str]:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=compose_dir, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {}
    states: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        try:
            svc = json.loads(line)
            states[svc.get("Service", "?")] = svc.get("State", "?")
        except (json.JSONDecodeError, KeyError):
            pass
    return states


def _verify_containers(compose_dir: Path, compose_file: Path) -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
        cwd=compose_dir, capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        _print_status(compose_dir, compose_file)
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Service", style="cyan")
    table.add_column("State")
    table.add_column("Ports", style="dim")

    any_problem = False
    for line in result.stdout.strip().splitlines():
        try:
            svc = json.loads(line)
            name = svc.get("Service", svc.get("Name", "?"))
            state = svc.get("State", "?")
            health = svc.get("Health", "")
            publishers = svc.get("Publishers") or []

            port_strs = [
                f"{p['PublishedPort']}→{p['TargetPort']}"
                for p in publishers if p.get("PublishedPort")
            ]

            if state == "running":
                label = "[green]running[/green]"
                if health == "healthy":
                    label += " [green](healthy)[/green]"
                elif health == "unhealthy":
                    label += " [red](unhealthy)[/red]"
                    any_problem = True
            else:
                label = f"[red]{state}[/red]"
                any_problem = True

            table.add_row(name, label, "  ".join(port_strs))
        except (json.JSONDecodeError, KeyError):
            pass

    console.print(table)
    if any_problem:
        console.print(
            "  [yellow]⚠ Some containers failed.[/yellow] "
            "Check logs: [dim]docker compose logs --tail=50[/dim]"
        )


def _print_status(compose_dir: Path, compose_file: Path) -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps"],
        cwd=compose_dir, capture_output=True, text=True,
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
