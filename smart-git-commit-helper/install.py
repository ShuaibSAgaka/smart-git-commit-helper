#!/usr/bin/env python3
"""
install.py — Install (or uninstall) the Smart Commit Helper as a
             prepare-commit-msg git hook in any target repository.

Usage:
    python install.py              # install into current repo
    python install.py /path/to/repo
    python install.py --uninstall
    python install.py --uninstall /path/to/repo
"""

import sys
import os
import stat
import shutil
import argparse
import subprocess

HOOK_NAME = "prepare-commit-msg"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Hook script template ──────────────────────────────────────────────────────

HOOK_TEMPLATE = """\
#!/bin/sh
# Smart Git Commit Helper — auto-installed by install.py
# https://github.com/YOUR_USERNAME/smart-git-commit-helper

SCRIPT_DIR="{script_dir}"
PYTHON="{python}"

if [ -f "$SCRIPT_DIR/main.py" ]; then
    "$PYTHON" "$SCRIPT_DIR/main.py" "$1" "$2" "$3"
    exit $?
else
    echo "[smart-commit] WARNING: main.py not found at $SCRIPT_DIR"
    exit 0
fi
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_git_root(start: str) -> str:
    r = subprocess.run(
        "git rev-parse --show-toplevel",
        shell=True, capture_output=True, text=True, cwd=start
    )
    if r.returncode != 0:
        print(f"ERROR: '{start}' is not inside a git repository.")
        sys.exit(1)
    return r.stdout.strip()


def _python_path() -> str:
    return sys.executable


# ── Install ───────────────────────────────────────────────────────────────────

def install(repo_path: str):
    git_root  = _find_git_root(repo_path)
    hooks_dir = os.path.join(git_root, ".git", "hooks")
    hook_path = os.path.join(hooks_dir, HOOK_NAME)

    os.makedirs(hooks_dir, exist_ok=True)

    # Backup existing hook if present and not ours
    if os.path.exists(hook_path):
        backup = hook_path + ".backup"
        with open(hook_path) as f:
            content = f.read()
        if "Smart Git Commit Helper" in content:
            print(f"  ✔  Hook already installed at {hook_path}")
        else:
            shutil.copy2(hook_path, backup)
            print(f"  ℹ  Existing hook backed up to {backup}")
    
    hook_content = HOOK_TEMPLATE.format(
        script_dir=SCRIPT_DIR,
        python=_python_path(),
    )

    with open(hook_path, "w", newline="\n") as f:
        f.write(hook_content)

    # Make executable (Linux/macOS)
    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"\n  ✔  Smart Commit Helper installed!")
    print(f"     Hook : {hook_path}")
    print(f"     Repo : {git_root}")
    print(f"\n  Now every [git commit] in this repo will trigger the wizard.\n")


# ── Uninstall ─────────────────────────────────────────────────────────────────

def uninstall(repo_path: str):
    git_root  = _find_git_root(repo_path)
    hook_path = os.path.join(git_root, ".git", "hooks", HOOK_NAME)

    if not os.path.exists(hook_path):
        print("  ℹ  No hook found — nothing to remove.")
        return

    with open(hook_path) as f:
        content = f.read()

    if "Smart Git Commit Helper" not in content:
        print("  ⚠  Hook at this path was not installed by us — leaving it alone.")
        return

    # Restore backup if it exists
    backup = hook_path + ".backup"
    if os.path.exists(backup):
        shutil.move(backup, hook_path)
        print(f"  ✔  Previous hook restored from backup.")
    else:
        os.remove(hook_path)
        print(f"  ✔  Hook removed from {hook_path}")

    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Install / uninstall Smart Git Commit Helper as a git hook"
    )
    parser.add_argument("repo", nargs="?", default=os.getcwd(),
                        help="Path to the target git repo (default: current directory)")
    parser.add_argument("--uninstall", action="store_true",
                        help="Remove the hook instead of installing it")
    args = parser.parse_args()

    print("\n  Smart Git Commit Helper — Hook Installer\n")

    if args.uninstall:
        uninstall(args.repo)
    else:
        install(args.repo)


if __name__ == "__main__":
    main()