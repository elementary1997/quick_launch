"""
Interactive credential prompt — shown when no token/key is found for a provider.
"""
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

console = Console()


def ask_and_save(provider_name: str, keys_dir: Path, token_file: str) -> str | None:
    """
    Prompt user for a token. Optionally save it to keys_dir/<token_file>.
    Returns the entered token, or None if the user skips.
    """
    console.print(
        f"\n[yellow]No credentials found for {provider_name}.[/yellow]\n"
        f"The repo may be private or rate-limited without a token."
    )
    skip = not Confirm.ask("Enter token now?", default=True)
    if skip:
        return None

    token = Prompt.ask(f"[cyan]{provider_name} token[/cyan]", password=True)
    if not token:
        return None

    if Confirm.ask(f"Save to [dim]keys/{token_file}[/dim] for future use?", default=True):
        keys_dir.mkdir(parents=True, exist_ok=True)
        dest = keys_dir / token_file
        dest.write_text(token)
        dest.chmod(0o600)
        console.print(f"[green]✓ Saved[/green] {dest}")

    return token
