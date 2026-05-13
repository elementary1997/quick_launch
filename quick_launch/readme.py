from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

_CANDIDATES = ["README.md", "README.rst", "README.txt", "README", "readme.md"]


def display(repo_dir: Path) -> None:
    for name in _CANDIDATES:
        path = repo_dir / name
        if path.exists():
            text = path.read_text(errors="replace")
            if name.endswith(".md"):
                content = Markdown(text)
            else:
                content = text  # type: ignore[assignment]
            console.print(Panel(content, title=f"[bold]{name}[/bold]", border_style="blue"))
            return
    console.print("[dim]No README found[/dim]")
