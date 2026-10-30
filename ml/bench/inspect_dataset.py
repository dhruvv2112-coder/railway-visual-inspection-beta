"""Inventory the Mendeley rail-defect dataset: folder tree, file types, class-name files, sample labels."""
import collections
from pathlib import Path

from common import REPORTS
from datasets import mendeley_rail_defects

root = mendeley_rail_defects()
out = []
out.append(f"ROOT {root}")
for p in sorted(root.rglob("*")):
    if p.is_dir():
        exts = collections.Counter(c.suffix.lower() for c in p.iterdir() if c.is_file())
        if exts or p.parent == root:
            out.append(f"DIR {p.relative_to(root)} {dict(exts)}")
for p in sorted(root.rglob("*")):
    if p.is_file() and p.suffix.lower() in {".yaml", ".yml", ".names", ".json", ".csv", ".md", ".txt"} and p.stat().st_size < 200_000:
        if p.suffix.lower() == ".txt" and p.parent.name.lower() in {"labels", "label"}:
            continue
        out.append(f"--- FILE {p.relative_to(root)} ({p.stat().st_size} B)")
        out.append(p.read_text(errors="replace")[:3000])
labels = [p for p in root.rglob("*.txt") if p.parent.name.lower() in {"labels", "label"}][:5]
for p in labels:
    out.append(f"--- LABEL {p.relative_to(root)}: {p.read_text()[:300]}")
xmls = list(root.rglob("*.xml"))[:2]
for p in xmls:
    out.append(f"--- XML {p.relative_to(root)}: {p.read_text()[:1500]}")
(REPORTS / "dataset_inventory.txt").write_text("\n".join(out))
print("\n".join(out[:400]))
