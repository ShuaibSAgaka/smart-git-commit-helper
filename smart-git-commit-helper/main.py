#!/usr/bin/env python3
"""
Runs as a prepare-commit-msg git hook.
Analyzes staged diff, generates a Conventional Commit message,
then opens an interactive Rich TUI to review/edit before committing.
"""

from commithelper.hook import run_hook
import sys

if __name__ == "__main__":
    # When run as a git hook:
    #   argv[1] = path to .git/COMMIT_EDITMSG
    #   argv[2] = source (optional: "message", "template", "merge", etc.)
    commit_msg_file = sys.argv[1] if len(sys.argv) > 1 else None
    source          = sys.argv[2] if len(sys.argv) > 2 else None
    run_hook(commit_msg_file, source)