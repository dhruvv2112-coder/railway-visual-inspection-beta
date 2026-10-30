"""Build one YOLO-format OHE dataset from public sources, mapped to the registry component names
(shared/ohe_registry.yaml). Splits keep each source's own split (CPLID splits keep UAV frame chains together).

Sources (HLD §12; licences recorded in the manifest):
  - KeenForgeAI/CPLID_Insulators-corrected  (insulator, defect)  upstream licence undetermined -> research only
  - docmhvr/powerline-components-and-faults (drone, YOLO)         MIT
Domain caveat: both are drone / transmission-line views, not ground-level 25 kV railway OHE."""
import json
import os
import re
import shutil
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download

OUT = Path(os.environ.get("OHE_DATA", ".cache/ohe")) / "ohe_yolo"
CAP = int(os.environ.get("OHE_CAP_PER_SOURCE", "1500"))  # cap train images per source for CPU CI
TARGET = ["insulator", "insulator_defect", "bird_nest", "vegetation", "dropper", "number_plate"]
SOURCES = [("KeenForgeAI/CPLID_Insulators-corrected", "undetermined (research only)"),
           ("docmhvr/powerline-components-and-faults", "MIT")]
IMG = {".jpg", ".jpeg", ".png", ".bmp"}


def map_name(n: str) -> str | None:
    n = n.lower()
    if "insulator" in n and re.search(r"defect|broken|damag|fault|flash|crack|missing", n):
        return "insulator_defect"
    if n in ("defect", "broken", "damaged"):
        return "insulator_defect"            # CPLID: 'defect' boxes mark missing insulator caps
    if "insulator" in n:
        return "insulator"
    if "nest" in n:
        return "bird_nest"
    if re.search(r"veget|tree|branch", n):
        return "vegetation"
    return None                               # other powerline hardware is outside the OHE registry scope


def class_names(root: Path) -> list[str]:
    for f in list(root.rglob("data.yaml")) + list(root.rglob("*.yaml")):
        try:
            names = yaml.safe_load(f.read_text()).get("names")
            if names:
                return list(names.values()) if isinstance(names, dict) else list(names)
        except Exception:
            pass
    for f in list(root.rglob("classes.txt")) + list(root.rglob("*.names")):
        return [x.strip() for x in f.read_text().splitlines() if x.strip()]
    raise RuntimeError(f"no class names in {root}")


def split_of(p: Path) -> str:
    parts = [x.lower() for x in p.parts]
    if any(x in ("val", "valid", "validation") for x in parts):
        return "val"
    if "test" in parts:
        return "test"
    return "train"


def label_for(img: Path) -> Path | None:
    cands = [img.with_suffix(".txt"), Path(str(img.with_suffix(".txt")).replace("/images/", "/labels/"))]
    return next((c for c in cands if c.exists()), None)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    manifest = {"target_names": TARGET, "sources": []}
    for repo, lic in SOURCES:
        root = Path(snapshot_download(repo, repo_type="dataset", local_dir=str(OUT.parent / repo.replace("/", "__"))))
        names = class_names(root)
        mapping = {i: map_name(n) for i, n in enumerate(names)}
        counts = {"train": 0, "val": 0, "test": 0}
        inst = {t: 0 for t in TARGET}
        for img in sorted(p for p in root.rglob("*") if p.suffix.lower() in IMG):
            lab = label_for(img)
            if lab is None:
                continue
            sp = split_of(img)
            if sp == "train" and counts["train"] >= CAP:
                continue
            lines = []
            for ln in lab.read_text().split("\n"):
                v = ln.split()
                if len(v) >= 5 and mapping.get(int(float(v[0]))):
                    t = mapping[int(float(v[0]))]
                    lines.append(" ".join([str(TARGET.index(t))] + v[1:5]))
                    inst[t] += 1
            name = f"{repo.split('/')[0][:6]}_{img.stem}{img.suffix.lower()}"
            for d in ("images", "labels"):
                (OUT / sp / d).mkdir(parents=True, exist_ok=True)
            shutil.copy(img, OUT / sp / "images" / name)
            (OUT / sp / "labels" / (Path(name).stem + ".txt")).write_text("\n".join(lines))
            counts[sp] += 1
        manifest["sources"].append({"repo": repo, "licence": lic, "source_names": names,
                                    "mapping": {names[i]: m for i, m in mapping.items()}, "images": counts, "instances": inst})
        print(repo, names, counts, inst, flush=True)
    (OUT / "data.yaml").write_text(yaml.safe_dump({"path": str(OUT.resolve()), "train": "train/images", "val": "val/images",
                                                   "test": "test/images", "names": TARGET}))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
