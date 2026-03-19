"""
Supprime les lignes de séparation décoratives (# ────...) et simplifie les
commentaires bannière (# ── Titre ──) en # Titre. Ne modifie que les lignes
dont le texte après # commence par le caractère U+2500 (─).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"venv", ".venv", "__pycache__", "node_modules", ".git"}


def transform_line(line: str) -> str | None:
    """Retourne la nouvelle ligne, None pour supprimer, ou ligne inchangée."""
    m = re.match(r"^(\s*)#\s*(.*)$", line)
    if not m:
        return line
    indent, rest = m.group(1), m.group(2)
    stripped = rest.strip()
    if not stripped.startswith("\u2500"):  # ─
        return line
    title = re.sub(r"^\u2500+\s*", "", stripped)
    title = re.sub(r"\s*\u2500{2,}$", "", title)
    if not title.strip():
        return None
    return f"{indent}# {title.strip()}"


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    changed = False
    for line in lines:
        nl = "\n" if line.endswith("\n") else ""
        if line.endswith("\r\n"):
            nl = "\r\n"
            core = line[:-2]
        elif line.endswith("\n"):
            core = line[:-1]
        else:
            core = line
        if core.lstrip().startswith("#"):
            new_core = transform_line(core)
            if new_core is None:
                changed = True
                continue
            if new_core != core:
                changed = True
            core = new_core
        out.append(core + nl)
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def main() -> int:
    changed_files: list[str] = []
    for p in ROOT.rglob("*.py"):
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        if process_file(p):
            changed_files.append(str(p.relative_to(ROOT)))
    print(f"Modified {len(changed_files)} file(s)")
    for f in sorted(changed_files):
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
