"""
SSH key discovery and interactive selection.
Called by CLI when check_access() returns has_auth=False.
"""
import shutil
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

console = Console()


def scan_available_keys(keys_dir: Path) -> list[Path]:
    """Return all private key files found in keys_dir and ~/.ssh/."""
    found: list[Path] = []
    seen: set[Path] = set()

    search_dirs = [keys_dir, Path.home() / ".ssh"]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if (
                p.is_file()
                and not p.suffix == ".pub"
                and p.name not in ("known_hosts", "config", "authorized_keys")
                and p.resolve() not in seen
            ):
                # Quick check: private keys start with "-----BEGIN"
                try:
                    header = p.read_bytes(27)
                    if header.startswith(b"-----BEGIN"):
                        found.append(p)
                        seen.add(p.resolve())
                except OSError:
                    pass

    return found


def ask_for_ssh_key(
    provider_name: str,
    keys_dir: Path,
    dest_key_name: str,
) -> Path | None:
    """
    Show available SSH keys, let user pick one or enter a custom path.
    Copies the selected key to keys_dir/<dest_key_name> and returns that path.
    Returns None if user skips.
    """
    keys_dir.mkdir(parents=True, exist_ok=True)
    available = scan_available_keys(keys_dir)

    console.print(f"\n[yellow]No SSH key found for {provider_name}.[/yellow]")

    if available:
        _print_key_table(available)
        console.print(f"  [dim]{len(available) + 1}[/dim]  Enter custom path")
        console.print(f"  [dim]{len(available) + 2}[/dim]  Skip")

        choice = IntPrompt.ask(
            "Select key",
            default=len(available) + 2,
        )

        if choice == len(available) + 2:
            return None
        if 1 <= choice <= len(available):
            selected = available[choice - 1]
        else:
            selected = _prompt_custom_path()
            if not selected:
                return None
    else:
        console.print("[dim]No keys found in keys/ or ~/.ssh/[/dim]")
        if not Confirm.ask("Enter key path manually?", default=False):
            return None
        selected = _prompt_custom_path()
        if not selected:
            return None

    dest = keys_dir / dest_key_name
    if selected.resolve() != dest.resolve():
        shutil.copy2(selected, dest)
        dest.chmod(0o600)
        console.print(f"[green]✓ Copied[/green] {selected.name} → keys/{dest_key_name}")

    return dest


def _print_key_table(keys: list[Path]) -> None:
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("#", style="dim", width=3)
    table.add_column("File", style="cyan")
    table.add_column("Location", style="dim")

    for i, k in enumerate(keys, 1):
        table.add_row(str(i), k.name, str(k.parent))

    console.print(table)


def _prompt_custom_path() -> Path | None:
    raw = Prompt.ask("Path to private key").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if not p.exists():
        console.print(f"[red]File not found: {p}[/red]")
        return None
    return p
