# ⚡ Smart Git Commit Helper
  
> A rule-based CLI tool that analyses your staged `git diff`, generates a **Conventional Commit** message, then opens a **Rich TUI** so you can review and edit it — all before the commit lands.  
> Runs automatically as a **`prepare-commit-msg` git hook**.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Rich](https://img.shields.io/badge/Rich-TUI-brightgreen?style=flat-square)
![Git Hook](https://img.shields.io/badge/Git-prepare--commit--msg-F05032?style=flat-square&logo=git&logoColor=white)
![No API](https://img.shields.io/badge/API-none%20required-lightgrey?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## ✨ What It Does

Every time you run `git commit`, the hook:

1. **Reads your staged diff** (`git diff --cached`)
2. **Analyses file names, statuses, and diff content** with rule-based heuristics
3. **Suggests a Conventional Commit message** with type, scope, and subject
4. **Opens an interactive TUI** where you can:
   - Accept the message as-is
   - Change the commit type (`feat`, `fix`, `docs`, `refactor`, …)
   - Edit the subject line
   - Edit the scope
   - Toggle the breaking-change marker (`!`)
   - Open the full message in your `$EDITOR`
   - Abort the commit
5. **Writes the final message** to `COMMIT_EDITMSG` and lets git proceed

---

## 🖥️ Demo

```
  SMART COMMIT  ·  Staged Changes

  ┌─────────────────────────────────────────────────────────┐
  │ File                     Status     +Lines   -Lines     │
  │ src/auth/login.py        MODIFIED   +42      -11        │
  │ tests/test_login.py      ADDED      +87      -0         │
  └─────────────────────────────────────────────────────────┘
  2 file(s)  +129  -11

  ── Generated Commit Message ──────────────────────────────
  TYPE  feat   CONFIDENCE  HIGH   SCOPE  src

  ╭─ commit message ────────────────────────────────────────╮
  │                                                         │
  │   feat(src): add login                                  │
  │                                                         │
  │   - src/auth/login.py [modified] +42/-11                │
  │   - tests/test_login.py [added] +87/-0                  │
  │                                                         │
  ╰─────────────────────────────────────────────────────────╯

  ── Edit Options ──────────────────────────────────────────
  1.  Use this message as-is
  2.  Change commit type
  3.  Edit subject line
  4.  Edit scope
  5.  Toggle breaking change (!)
  6.  Open full message in editor
  7.  Abort commit

  Choice [1]:
```

---

## 🚀 Quick Start

### 1. Clone & install dependency

```bash
git clone https://github.com/YOUR_USERNAME/smart-git-commit-helper.git
cd smart-git-commit-helper
pip install rich
```

### 2. Install the hook into any repo

```bash
# Install into the current repo
python install.py

# Install into a specific repo
python install.py /path/to/your-project

# Uninstall
python install.py --uninstall
```

### 3. Commit as normal

```bash
cd /path/to/your-project
git add .
git commit      # ← wizard runs automatically
```

---

## 📁 Project Structure

```
smart-git-commit-helper/
├── main.py                  # Hook entry point (called by git)
├── install.py               # One-command hook installer / uninstaller
├── requirements.txt
└── commithelper/
    ├── __init__.py
    ├── analyzer.py          # Staged diff parser + rule-based message generator
    ├── editor.py            # Rich TUI (preview + interactive edit menu)
    └── hook.py              # Orchestrates analyze → preview → edit → write
```

---

## 🧠 How the Rule Engine Works

The generator votes on a commit type by scoring signals from:

| Signal source | Example |
|---|---|
| **File extensions** | `.md` → `docs`, `_test.py` → `test` |
| **File names** | `Dockerfile` → `chore`, `package.json` → `build` |
| **File status** | Added files → `feat`, deleted → `chore` |
| **Diff content keywords** | `fix`, `bug` → `fix` · `add`, `implement` → `feat` |
| **Special markers** | `BREAKING CHANGE` in diff → breaking flag |

The type with the most votes wins. Confidence (`HIGH` / `MED` / `LOW`) reflects how decisive the vote was.

---

## 📋 Supported Commit Types

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Neither fix nor feature |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `chore` | Tooling, deps, build |
| `ci` | CI/CD config |
| `build` | Build system changes |
| `revert` | Reverts a previous commit |

---

## 🗺️ Roadmap

- [ ] AI-powered message generation via Claude API (optional flag)
- [ ] `--dry-run` mode (preview without committing)
- [ ] Config file (`~/.smart-commit.yml`) for custom type rules
- [ ] Emoji prefix support per type
- [ ] Multi-repo bulk install script

---

## 📄 License

MIT © Shuaib S. Agaka

---

> Part of my [30-Day GitHub Build Roadmap](https://github.com/ShuaibSAgaka) — building and shipping one project every day.
