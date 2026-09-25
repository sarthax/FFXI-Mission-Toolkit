#!/usr/bin/env python3
"""Index durable DSP engine-change records into a machine-readable audit index."""
from __future__ import annotations
import argparse, json, re
from dataclasses import asdict, dataclass, field
from pathlib import Path

DIFF_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
HUNK_RE = re.compile(r"^@@ .*? @@(?:\s*(.*))?$", re.MULTILINE)
SYMBOL_RE = re.compile(
    r"^\+\s*(?:class|struct|enum(?: class)?|"
    r"(?:static\s+)?(?:inline\s+)?[A-Za-z_][\w:<>,*&\s]+\s+)?"
    r"([A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)

@dataclass
class EngineChange:
    change_id: str
    path: str
    readme_present: bool
    diff_present: bool
    evidence_status: str
    changed_files: list[str] = field(default_factory=list)
    hunks: list[str] = field(default_factory=list)
    symbol_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

def parse_diff(diff_text: str):
    files = []
    for a, b in DIFF_FILE_RE.findall(diff_text):
        files.append(b if b != "/dev/null" else a)
    hunks = [m.group(1).strip() for m in HUNK_RE.finditer(diff_text) if m.group(1)]
    symbols = sorted(set(m.group(1) for m in SYMBOL_RE.finditer(diff_text)))
    return sorted(set(files)), hunks, symbols

def classify(readme, diff, diff_text):
    notes = []
    if not readme and not diff:
        return "INCOMPLETE", ["Missing README.md and .diff evidence."]
    if not readme:
        notes.append("Missing README.md: rationale/verification evidence is incomplete.")
    if not diff:
        notes.append("Missing scoped .diff: durable implementation evidence is incomplete.")
    if diff and ("placeholder" in diff_text.lower() or "template" in diff_text.lower()):
        notes.append("Diff appears to be placeholder/template text rather than a real patch.")
        return "TEMPLATE", notes
    return ("RECORDED" if readme and diff else "PARTIAL"), notes

def index(root: Path):
    out = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        readme_path = d / "README.md"
        diffs = sorted(d.glob("*.diff"))
        diff_path = diffs[0] if diffs else None
        readme = readme_path.is_file()
        diff = diff_path is not None
        diff_text = diff_path.read_text(encoding="utf-8", errors="replace") if diff_path else ""
        files, hunks, symbols = parse_diff(diff_text)
        status, notes = classify(readme, diff, diff_text)
        if len(diffs) > 1:
            notes.append(f"Multiple diff files found ({len(diffs)}); index currently uses the first lexically.")
        out.append(EngineChange(d.name, str(d.relative_to(root)), readme, diff, status, files, hunks, symbols, notes))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--markdown", type=Path, default=None)
    args = ap.parse_args()
    records = index(args.root)
    payload = {"schema": 1, "source": str(args.root), "records": [asdict(r) for r in records]}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# DSP Engine Change Index", "", f"Records: {len(records)}", ""]
        for r in records:
            lines += [f"## {r.change_id}", f"- Status: **{r.evidence_status}**",
                      f"- README: {'yes' if r.readme_present else 'NO'}",
                      f"- Diff: {'yes' if r.diff_present else 'NO'}"]
            if r.changed_files:
                lines.append("- Changed files: " + ", ".join(f"{x}" for x in r.changed_files))
            if r.symbol_hints:
                lines.append("- Symbol hints: " + ", ".join(f"{x}" for x in r.symbol_hints))
            for note in r.notes:
                lines.append(f"- Note: {note}")
            lines.append("")
        args.markdown.write_text("\n".join(lines), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
