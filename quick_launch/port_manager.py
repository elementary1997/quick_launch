"""
Check compose port bindings for host conflicts and remap to free ports.
Writes docker-compose.override.yml so docker compose merges it automatically.
"""
import socket
from dataclasses import dataclass
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class PortRemap:
    service: str
    original: int   # port that was requested
    assigned: int   # free port actually used
    container: int  # port inside the container (unchanged)


def ensure_ports_free(compose_file: Path, work_dir: Path) -> list[PortRemap]:
    """
    Scan all host ports declared in compose_file.
    Remap any that are occupied, write docker-compose.override.yml if needed.
    Returns list of remappings so callers can show updated URLs.
    """
    data = _load(compose_file)
    remaps: list[PortRemap] = []

    for svc_name, svc in (data.get("services") or {}).items():
        for entry in (svc or {}).get("ports") or []:
            host_port, container_port = _parse(entry)
            if host_port is None:
                continue
            if not _is_free(host_port):
                new_port = _find_free(host_port)
                remaps.append(PortRemap(svc_name, host_port, new_port, container_port))

    if remaps:
        _show_table(remaps)
        _write_override(work_dir, remaps)

    return remaps


def get_effective_ports(compose_file: Path, work_dir: Path) -> list[tuple[str, int, int]]:
    """
    Return (service, host_port, container_port) for all mapped ports,
    taking any existing override into account.
    """
    base = _load(compose_file)
    override_file = work_dir / "docker-compose.override.yml"
    overrides: dict[str, list[str]] = {}
    if override_file.exists():
        ov = _load(override_file)
        for svc, cfg in (ov.get("services") or {}).items():
            overrides[svc] = [str(p) for p in (cfg or {}).get("ports") or []]

    results: list[tuple[str, int, int]] = []
    for svc, cfg in (base.get("services") or {}).items():
        for entry in (cfg or {}).get("ports") or []:
            if svc in overrides:
                continue  # will be read from override
            h, c = _parse(entry)
            if h:
                results.append((svc, h, c))
        if svc in overrides:
            for entry in overrides[svc]:
                h, c = _parse(entry)
                if h:
                    results.append((svc, h, c))
    return results


# ── internals ────────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _parse(entry) -> tuple[int | None, int]:
    """Return (host_port_or_None, container_port) from a compose ports entry."""
    if isinstance(entry, int):
        return entry, entry
    if isinstance(entry, str):
        parts = entry.split(":")
        try:
            if len(parts) >= 2:
                host = int(parts[-2].split(".")[-1])  # handle "127.0.0.1:8080"
                cont = int(parts[-1].split("/")[0])
                return host, cont
            return int(parts[0]), int(parts[0])
        except (ValueError, IndexError):
            return None, 0
    if isinstance(entry, dict):
        host = entry.get("published")
        cont = entry.get("target", 0)
        return (int(host) if host else None), int(cont)
    return None, 0


def _is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def _find_free(preferred: int) -> int:
    if preferred < 1024:
        # Privileged port — remap to unprivileged range (80→8080, 443→8443, etc.)
        base = preferred + 8000
        for delta in range(300):
            candidate = base + delta
            if candidate <= 65535 and _is_free(candidate):
                return candidate
    else:
        for delta in range(1, 300):
            for candidate in (preferred + delta, preferred - delta):
                if 1024 <= candidate <= 65535 and _is_free(candidate):
                    return candidate
    raise RuntimeError(f"No free port found near {preferred}")


def _write_override(work_dir: Path, remaps: list[PortRemap]) -> None:
    services: dict = {}
    for r in remaps:
        services.setdefault(r.service, {"ports": []})
        services[r.service]["ports"].append(f"{r.assigned}:{r.container}")

    override_path = work_dir / "docker-compose.override.yml"
    # Merge with existing override if present
    existing: dict = {}
    if override_path.exists():
        try:
            existing = yaml.safe_load(override_path.read_text()) or {}
        except Exception:
            pass
    for svc, cfg in services.items():
        existing.setdefault("services", {}).setdefault(svc, {})
        existing["services"][svc]["ports"] = cfg["ports"]

    override_path.write_text(yaml.dump(existing, default_flow_style=False))
    console.print(f"  [dim]→ wrote {override_path.name}[/dim]")


def _show_table(remaps: list[PortRemap]) -> None:
    table = Table(box=None, show_header=True, header_style="dim", padding=(0, 2))
    table.add_column("Service", style="cyan")
    table.add_column("Requested", style="red")
    table.add_column("")
    table.add_column("Assigned", style="green")
    for r in remaps:
        table.add_row(r.service, f":{r.original}", "→", f":{r.assigned}")
    console.print("  [yellow]⚠ Port conflicts — remapping:[/yellow]")
    console.print(table)
