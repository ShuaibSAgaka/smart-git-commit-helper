"""
analyzer.py — Parse git staged diff and generate a Conventional Commit message
using pure rule-based heuristics. No API needed.
"""

import subprocess
import re
import os
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


# ── Conventional Commit types ─────────────────────────────────────────────────

COMMIT_TYPES = {
    "feat":     "A new feature",
    "fix":      "A bug fix",
    "docs":     "Documentation only changes",
    "style":    "Formatting, missing semicolons, etc — no logic change",
    "refactor": "Code change that neither fixes a bug nor adds a feature",
    "perf":     "A code change that improves performance",
    "test":     "Adding or correcting tests",
    "chore":    "Build process, tooling, or dependency updates",
    "ci":       "CI/CD configuration changes",
    "build":    "Changes affecting build system or external dependencies",
    "revert":   "Reverts a previous commit",
}

# File pattern → commit type hints
TYPE_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\.(md|rst|txt|adoc)$",           re.I), "docs"),
    (re.compile(r"(test_|_test|\.test\.|\.spec\.)", re.I), "test"),
    (re.compile(r"(\.github|\.travis|\.circleci|jenkinsfile|\.gitlab-ci)", re.I), "ci"),
    (re.compile(r"(requirements.*\.txt|pyproject\.toml|package\.json|poetry\.lock|yarn\.lock|Pipfile)", re.I), "build"),
    (re.compile(r"(makefile|dockerfile|docker-compose|\.env)",  re.I), "chore"),
    (re.compile(r"\.(css|scss|less|sass)$",         re.I), "style"),
    (re.compile(r"\.(perf|bench|benchmark)\.",      re.I), "perf"),
]

# Keyword patterns in diff content → type hints
CONTENT_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bfix(ed|es|ing)?\b|\bbug\b|\bpatch\b",       re.I), "fix"),
    (re.compile(r"\badd(ed|ing|s)?\b|\bnew\b|\bfeature\b|\bimplement", re.I), "feat"),
    (re.compile(r"\brefactor(ed|ing)?\b|\bclean(up)?\b|\bmove\b|\brename\b", re.I), "refactor"),
    (re.compile(r"\bperf(ormance)?\b|\boptimize?\b|\bspeed\b|\bcache\b", re.I), "perf"),
    (re.compile(r"\btest(s|ing|ed)?\b|\bassert\b|\bexpect\b",   re.I), "test"),
    (re.compile(r"\bdoc(s|ument)?\b|\bcomment\b|\breadme\b",    re.I), "docs"),
    (re.compile(r"\brevert\b|\bundone?\b|\brollback\b",         re.I), "revert"),
]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FileChange:
    path: str
    status: str          # A=added, M=modified, D=deleted, R=renamed, C=copied
    additions: int = 0
    deletions: int = 0
    diff_snippet: str = ""
    extension: str = ""
    basename: str = ""

    def __post_init__(self):
        self.extension = os.path.splitext(self.path)[1].lower()
        self.basename  = os.path.basename(self.path)


@dataclass
class DiffSummary:
    files: list[FileChange] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    raw_diff: str = ""
    is_empty: bool = True

    @property
    def scope_guess(self) -> Optional[str]:
        """Best-guess scope from the most common directory or filename."""
        if not self.files:
            return None
        dirs = [os.path.dirname(f.path) for f in self.files if os.path.dirname(f.path)]
        if dirs:
            from collections import Counter
            common = Counter(dirs).most_common(1)[0][0]
            # Use only the first path segment as scope
            parts = common.replace("\\", "/").split("/")
            return parts[0] if parts and parts[0] not in (".", "") else None
        # Fallback: stem of first file
        return os.path.splitext(self.files[0].basename)[0] if self.files else None


@dataclass
class CommitSuggestion:
    type: str
    scope: Optional[str]
    subject: str
    body: str
    breaking: bool = False
    confidence: str = "medium"   # low / medium / high

    def formatted(self, include_body: bool = True) -> str:
        header = self.type
        if self.scope:
            header += f"({self.scope})"
        if self.breaking:
            header += "!"
        header += f": {self.subject}"
        if include_body and self.body:
            return f"{header}\n\n{self.body}"
        return header


# ── Git helpers ───────────────────────────────────────────────────────────────

def _run(cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def get_staged_diff() -> DiffSummary:
    """Return a DiffSummary of everything currently staged (git add'd)."""
    summary = DiffSummary()

    # Check if inside a git repo
    code, _ = _run("git rev-parse --is-inside-work-tree")
    if code != 0:
        return summary

    # Staged file status
    code, status_out = _run("git diff --cached --name-status")
    if code != 0 or not status_out:
        return summary

    summary.is_empty = False

    # Full diff text (limit to 8 KB to stay fast)
    _, raw = _run("git diff --cached --unified=3")
    summary.raw_diff = raw[:8192]

    # Per-file numstat
    _, numstat = _run("git diff --cached --numstat")
    numstat_map: dict[str, tuple[int, int]] = {}
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                adds = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
                numstat_map[parts[2]] = (adds, dels)
            except ValueError:
                pass

    # Build FileChange list
    for line in status_out.splitlines():
        parts = line.split("\t")
        status_char = parts[0][0]
        path = parts[-1]   # for renames, last field is new path

        adds, dels = numstat_map.get(path, (0, 0))
        summary.total_additions += adds
        summary.total_deletions += dels

        fc = FileChange(path=path, status=status_char, additions=adds, deletions=dels)
        summary.files.append(fc)

    # Attach per-file diff snippet (first 300 chars of that file's hunk)
    if summary.raw_diff:
        _attach_snippets(summary)

    return summary


def _attach_snippets(summary: DiffSummary):
    """Slice diff text per file and attach a snippet to each FileChange."""
    current_file: Optional[str] = None
    buffer: list[str] = []
    snippets: dict[str, str] = {}

    for line in summary.raw_diff.splitlines():
        if line.startswith("diff --git"):
            if current_file and buffer:
                snippets[current_file] = "\n".join(buffer)[:300]
            buffer = []
            # Extract filename: diff --git a/foo b/foo
            m = re.search(r" b/(.+)$", line)
            current_file = m.group(1) if m else None
        elif current_file:
            buffer.append(line)

    if current_file and buffer:
        snippets[current_file] = "\n".join(buffer)[:300]

    for fc in summary.files:
        fc.diff_snippet = snippets.get(fc.path, "")


# ── Rule-based message generator ─────────────────────────────────────────────

def _vote_type(summary: DiffSummary) -> dict[str, int]:
    votes: dict[str, int] = defaultdict(int)

    for fc in summary.files:
        for pattern, t in TYPE_HINTS:
            if pattern.search(fc.path):
                votes[t] += 2

        for pattern, t in CONTENT_HINTS:
            if pattern.search(fc.diff_snippet):
                votes[t] += 1

        # Status-based hints
        if fc.status == "A":
            votes["feat"] += 1
        elif fc.status == "D":
            votes["chore"] += 1

    # Diff-level content hints (whole diff)
    for pattern, t in CONTENT_HINTS:
        if pattern.search(summary.raw_diff[:2000]):
            votes[t] += 1

    return votes


def _build_subject(summary: DiffSummary, commit_type: str) -> str:
    files = summary.files
    n = len(files)

    if n == 0:
        return "update codebase"

    added    = [f for f in files if f.status == "A"]
    deleted  = [f for f in files if f.status == "D"]
    modified = [f for f in files if f.status == "M"]
    renamed  = [f for f in files if f.status == "R"]

    # Single file
    if n == 1:
        fc = files[0]
        stem = os.path.splitext(fc.basename)[0]
        if fc.status == "A":
            return f"add {stem}"
        if fc.status == "D":
            return f"remove {stem}"
        if fc.status == "R":
            return f"rename {stem}"
        # Modified — try to pull a meaningful verb from the diff
        verbs = re.findall(r"\b(add|remove|fix|update|refactor|improve|rename|move|delete|replace|clean)\w*\b",
                           fc.diff_snippet, re.I)
        if verbs:
            return f"{verbs[0].lower()} {stem}"
        return f"update {stem}"

    # Multiple files — describe the set
    parts = []
    if added:
        names = ", ".join(os.path.splitext(f.basename)[0] for f in added[:2])
        extra = f" and {len(added)-2} more" if len(added) > 2 else ""
        parts.append(f"add {names}{extra}")
    if deleted:
        parts.append(f"remove {len(deleted)} file(s)")
    if modified:
        if len(modified) == 1:
            parts.append(f"update {os.path.splitext(modified[0].basename)[0]}")
        else:
            parts.append(f"update {len(modified)} files")
    if renamed:
        parts.append(f"rename {len(renamed)} file(s)")

    subject = "; ".join(parts) if parts else f"update {n} files"
    # Keep under 72 chars
    return subject[:69] + "..." if len(subject) > 72 else subject


def _build_body(summary: DiffSummary) -> str:
    lines = []
    for fc in summary.files:
        status_label = {
            "A": "added", "M": "modified", "D": "deleted",
            "R": "renamed", "C": "copied",
        }.get(fc.status, fc.status)
        stat = f"+{fc.additions}/-{fc.deletions}" if (fc.additions or fc.deletions) else ""
        lines.append(f"- {fc.path} [{status_label}] {stat}".strip())
    return "\n".join(lines)


def generate_suggestion(summary: DiffSummary) -> CommitSuggestion:
    if summary.is_empty:
        return CommitSuggestion(
            type="chore", scope=None,
            subject="no staged changes detected",
            body="", confidence="low"
        )

    votes = _vote_type(summary)
    if votes:
        commit_type = max(votes, key=votes.get)
        top_score   = votes[commit_type]
        second      = sorted(votes.values(), reverse=True)
        confidence  = "high" if (len(second) < 2 or top_score >= second[1] * 2) else "medium"
    else:
        commit_type = "chore"
        confidence  = "low"

    scope   = summary.scope_guess
    subject = _build_subject(summary, commit_type)
    body    = _build_body(summary)

    # Detect potential breaking change: large deletions, "BREAKING" keyword
    breaking = (
        "BREAKING" in summary.raw_diff or
        summary.total_deletions > 100
    )

    return CommitSuggestion(
        type=commit_type,
        scope=scope,
        subject=subject,
        body=body,
        breaking=breaking,
        confidence=confidence,
    )