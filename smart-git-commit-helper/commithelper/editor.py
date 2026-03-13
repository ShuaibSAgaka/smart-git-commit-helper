"""
editor.py — Interactive Rich TUI for reviewing and editing the commit message.
"""

import os
import subprocess
import tempfile
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.rule import Rule
from rich.align import Align
from rich import box
from rich.prompt import Prompt, Confirm

from .analyzer import CommitSuggestion, DiffSummary, COMMIT_TYPES

console = Console()

# ── Palette (all literal strings — no f-string color injection) ───────────────
BANNER = r"""
  ███████╗███╗   ███╗ █████╗ ██████╗ ████████╗     ██████╗ ██████╗ ███╗   ███╗███╗   ███╗██╗████████╗
  ██╔════╝████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝    ██╔════╝██╔═══██╗████╗ ████║████╗ ████║██║╚══██╔══╝
  ███████╗██╔████╔██║███████║██████╔╝   ██║       ██║     ██║   ██║██╔████╔██║██╔████╔██║██║   ██║
  ╚════██║██║╚██╔╝██║██╔══██║██╔══██╗   ██║       ██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██║   ██║
  ███████║██║ ╚═╝ ██║██║  ██║██║  ██║   ██║       ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║   ██║
  ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝        ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝   ╚═╝
"""

CONFIDENCE_STYLE = {
    "high":   ("bright_green",  "HIGH"),
    "medium": ("yellow",        "MED"),
    "low":    ("bright_red",    "LOW"),
}

STATUS_LABELS = {
    "A": ("bright_green",  "ADDED"),
    "M": ("yellow",        "MODIFIED"),
    "D": ("bright_red",    "DELETED"),
    "R": ("cyan",          "RENAMED"),
    "C": ("magenta",       "COPIED"),
}


def _escape(v) -> str:
    return str(v).replace("[", "\\[").replace("]", "\\]")


def print_banner():
    console.print(BANNER, style="bold bright_yellow", highlight=False)
    console.print(
        Align.center(Text("⚡  Smart Git Commit Helper  ·  Conventional Commits  ·  Rule-based", style="bold cyan"))
    )
    console.print(Align.center(Text("─" * 72, style="grey50")))
    console.print()


def print_diff_summary(summary: DiffSummary):
    console.print(Rule("[bold white] Staged Changes [/bold white]", style="grey30"))
    console.print()

    if summary.is_empty:
        console.print("  [bright_red]No staged changes found.[/bright_red]  Run [bold]git add <files>[/bold] first.")
        return

    table = Table(box=box.SIMPLE_HEAD, border_style="grey30", expand=True,
                  header_style="bold white", show_edge=False)
    table.add_column("File",       style="white",        min_width=30)
    table.add_column("Status",     justify="center",     min_width=10)
    table.add_column("Additions",  justify="right",      style="bright_green", min_width=8)
    table.add_column("Deletions",  justify="right",      style="bright_red",   min_width=8)

    for fc in summary.files:
        color, label = STATUS_LABELS.get(fc.status, ("white", fc.status))
        status_text  = f"[{color}]{label}[/{color}]"
        table.add_row(
            _escape(fc.path),
            status_text,
            f"+{fc.additions}",
            f"-{fc.deletions}",
        )

    console.print(table)
    console.print(
        f"  [dim]{len(summary.files)} file(s)  "
        f"[bright_green]+{summary.total_additions}[/bright_green]  "
        f"[bright_red]-{summary.total_deletions}[/bright_red][/dim]"
    )
    console.print()


def print_suggestion(suggestion: CommitSuggestion):
    console.print(Rule("[bold white] Generated Commit Message [/bold white]", style="grey30"))
    console.print()

    conf_color, conf_label = CONFIDENCE_STYLE.get(suggestion.confidence, ("white", "?"))

    # Header line
    header_text = Text()
    header_text.append("  TYPE    ", style="dim")
    header_text.append(f" {suggestion.type} ", style="bold black on bright_green")
    header_text.append("  CONFIDENCE  ", style="dim")
    header_text.append(f" {conf_label} ", style=f"bold black on {conf_color}")
    if suggestion.scope:
        header_text.append("  SCOPE  ", style="dim")
        header_text.append(f" {_escape(suggestion.scope)} ", style="bold black on cyan")
    if suggestion.breaking:
        header_text.append("  BREAKING CHANGE ", style="bold black on bright_red")
    console.print(header_text)
    console.print()

    # The formatted message in a panel
    msg = _escape(suggestion.formatted())
    console.print(
        Panel(
            msg,
            border_style="bright_green",
            padding=(1, 3),
            title="[bold bright_green] commit message [/bold bright_green]",
        )
    )
    console.print()


def _type_picker(current: str) -> str:
    """Let user pick a Conventional Commit type from a numbered list."""
    console.print()
    console.print("  [bold cyan]Available types:[/bold cyan]")
    type_list = list(COMMIT_TYPES.items())
    for i, (t, desc) in enumerate(type_list, 1):
        marker = "[bold bright_green]>[/bold bright_green]" if t == current else " "
        console.print(f"  {marker} [bold]{i:>2}.[/bold]  [bold white]{t:<10}[/bold white]  [dim]{desc}[/dim]")
    console.print()

    while True:
        raw = Prompt.ask(
            "  [bold cyan]Pick type[/bold cyan] [dim](number or name, Enter to keep current)[/dim]",
            default=current,
            console=console,
        )
        if raw == current or raw == "":
            return current
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(type_list):
                return type_list[idx][0]
        elif raw in COMMIT_TYPES:
            return raw
        console.print("  [bright_red]Invalid choice — enter a number or type name.[/bright_red]")


def _open_in_editor(text: str) -> str:
    """Open the commit message in $EDITOR (fallback: notepad on Windows, nano on Unix)."""
    editor = os.environ.get("GIT_EDITOR") or os.environ.get("EDITOR") or (
        "notepad" if os.name == "nt" else "nano"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        fname = f.name
    try:
        subprocess.call([editor, fname])
        with open(fname, encoding="utf-8") as f:
            return f.read().strip()
    finally:
        os.unlink(fname)


def interactive_edit(suggestion: CommitSuggestion) -> Optional[str]:
    """
    Full interactive editor loop.
    Returns the final commit message string, or None if user aborts.
    """
    current = suggestion

    while True:
        console.print(Rule("[bold white] Edit Options [/bold white]", style="grey30"))
        console.print()
        console.print("  [bold white]What would you like to do?[/bold white]")
        console.print()
        console.print("  [bold bright_green]1.[/bold bright_green]  [white]Use this message as-is[/white]")
        console.print("  [bold yellow]2.[/bold yellow]  [white]Change commit type[/white]")
        console.print("  [bold yellow]3.[/bold yellow]  [white]Edit subject line[/white]")
        console.print("  [bold yellow]4.[/bold yellow]  [white]Edit scope[/white]")
        console.print("  [bold yellow]5.[/bold yellow]  [white]Toggle breaking change (!)[/white]")
        console.print("  [bold yellow]6.[/bold yellow]  [white]Open full message in editor[/white]")
        console.print("  [bold bright_red]7.[/bold bright_red]  [white]Abort commit[/white]")
        console.print()

        choice = Prompt.ask(
            "  [bold cyan]Choice[/bold cyan]",
            choices=["1","2","3","4","5","6","7"],
            default="1",
            console=console,
        )

        if choice == "1":
            return current.formatted()

        elif choice == "2":
            new_type = _type_picker(current.type)
            current = CommitSuggestion(
                type=new_type, scope=current.scope,
                subject=current.subject, body=current.body,
                breaking=current.breaking, confidence=current.confidence
            )

        elif choice == "3":
            new_subject = Prompt.ask(
                "  [bold cyan]New subject[/bold cyan]",
                default=current.subject,
                console=console,
            )
            current = CommitSuggestion(
                type=current.type, scope=current.scope,
                subject=new_subject.strip(), body=current.body,
                breaking=current.breaking, confidence=current.confidence
            )

        elif choice == "4":
            new_scope = Prompt.ask(
                "  [bold cyan]Scope[/bold cyan] [dim](leave blank to remove)[/dim]",
                default=current.scope or "",
                console=console,
            )
            current = CommitSuggestion(
                type=current.type, scope=new_scope.strip() or None,
                subject=current.subject, body=current.body,
                breaking=current.breaking, confidence=current.confidence
            )

        elif choice == "5":
            current = CommitSuggestion(
                type=current.type, scope=current.scope,
                subject=current.subject, body=current.body,
                breaking=not current.breaking, confidence=current.confidence
            )
            state = "ENABLED" if current.breaking else "DISABLED"
            console.print(f"  [yellow]Breaking change marker {state}.[/yellow]")

        elif choice == "6":
            edited = _open_in_editor(current.formatted())
            if edited:
                console.print()
                console.print(
                    Panel(_escape(edited), border_style="cyan",
                          title="[bold cyan] edited message [/bold cyan]", padding=(1, 3))
                )
                if Confirm.ask("  [bold cyan]Use this edited message?[/bold cyan]",
                               default=True, console=console):
                    return edited
            continue

        elif choice == "7":
            console.print()
            console.print("  [bright_red]Commit aborted.[/bright_red]")
            return None

        # Refresh preview after edits
        console.print()
        print_suggestion(current)