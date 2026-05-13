"""
Handle .env files: discover example files, fill defaults, display auth params.
"""
import re
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

# Keys that likely contain credentials worth highlighting
_AUTH_PATTERNS = re.compile(
    r"(password|passwd|secret|token|key|api_key|auth|user|login|host|port|db|database|dsn|url|uri)",
    re.IGNORECASE,
)

_EXAMPLE_CANDIDATES = [".env.example", ".env.sample", ".env.template", ".env.dist"]


def prepare(repo_dir: Path) -> Path | None:
    """Find .env.example, copy to .env if missing, fill blanks, display summary."""
    env_path = repo_dir / ".env"
    example_path = _find_example(repo_dir)

    if example_path:
        defaults = _parse(example_path)
        console.print(f"[cyan]Found template:[/cyan] {example_path.name}")
    else:
        defaults: dict[str, str] = {}

    if env_path.exists():
        console.print(f"[green].env already exists[/green] at {env_path}")
        merged = {**defaults, **_parse(env_path)}
    else:
        if not defaults:
            console.print("[dim]No .env or template found — skipping env setup[/dim]")
            return None
        merged = defaults
        _write(env_path, merged)
        console.print(f"[green]✓ Created[/green] {env_path} from template")

    _display_table(merged)
    return env_path


def _find_example(repo_dir: Path) -> Path | None:
    for name in _EXAMPLE_CANDIDATES:
        p = repo_dir / name
        if p.exists():
            return p
    return None


def _parse(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def _write(path: Path, data: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n")


def _display_table(data: dict[str, str]) -> None:
    table = Table(title="Environment variables", show_header=True, header_style="bold magenta")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value")
    table.add_column("Note", style="dim")

    for key, val in sorted(data.items()):
        is_auth = bool(_AUTH_PATTERNS.search(key))
        display_val = val if val else "[red]<EMPTY>[/red]"
        note = "[yellow]⚑ auth param[/yellow]" if is_auth else ""
        table.add_row(key, display_val, note)

    console.print(table)
