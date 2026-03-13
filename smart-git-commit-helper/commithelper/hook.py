"""
hook.py — Core logic called by the prepare-commit-msg git hook.
"""

import sys
import os
from typing import Optional

from .analyzer import get_staged_diff, generate_suggestion
from .editor import (
    console, print_banner, print_diff_summary,
    print_suggestion, interactive_edit
)


def run_hook(commit_msg_file: Optional[str], source: Optional[str]):
    """
    Entry point for the prepare-commit-msg hook.

    commit_msg_file : path to .git/COMMIT_EDITMSG
    source          : "message" | "template" | "merge" | "squash" | None
    """

    # Skip for merges, squashes, and amends that already have a message
    if source in ("merge", "squash", "commit"):
        sys.exit(0)

    print_banner()

    # 1. Analyse staged diff
    summary = get_staged_diff()
    print_diff_summary(summary)

    if summary.is_empty:
        console.print("  [yellow]Nothing staged — skipping commit message generation.[/yellow]")
        console.print("  [dim]Stage files with [bold]git add[/bold] then try again.[/dim]\n")
        sys.exit(1)   # abort the commit

    # 2. Generate suggestion
    suggestion = generate_suggestion(summary)
    print_suggestion(suggestion)

    # 3. Interactive TUI — let user accept / edit / abort
    final_message = interactive_edit(suggestion)

    if final_message is None:
        # User chose to abort
        sys.exit(1)

    # 4. Write final message back to COMMIT_EDITMSG
    if commit_msg_file:
        try:
            with open(commit_msg_file, "w", encoding="utf-8") as f:
                f.write(final_message + "\n")
            console.print()
            console.print("  [bold bright_green]✔[/bold bright_green]  Commit message written — proceeding with commit.")
            console.print()
        except OSError as e:
            console.print(f"  [bright_red]Error writing commit message file: {e}[/bright_red]")
            sys.exit(1)
    else:
        # Fallback: called directly from CLI (not as a hook)
        console.print()
        console.print("  [bold bright_green]Final message:[/bold bright_green]")
        console.print()
        console.print(f"  [white]{final_message}[/white]")
        console.print()