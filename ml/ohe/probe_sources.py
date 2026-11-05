"""Print what new candidate datasets contain (files, classes, licences) so loaders can be written (run in CI)."""
import json
import re
import urllib.request

from huggingface_hub import HfApi, hf_hub_download

api = HfApi()


def hf(repo):
    try:
        info = api.dataset_info(repo, files_metadata=False)
        files = [s.rfilename for s in info.siblings]
        exts = {}
        for f in files:
            e = f.rsplit(".", 1)[-1].lower() if "." in f else "-"
            exts[e] = exts.get(e, 0) + 1
        dirs = sorted({"/".join(f.split("/")[:3]) for f in files})
        print(f"\n===== hf {repo}\nlicense={(info.card_data or {}).get('license') if info.card_data else None} "
              f"n_files={len(files)} exts={exts}\ndirs={dirs[:60]}", flush=True)
        for f in [f for f in files if re.search(r"(data|dataset)\.ya?ml$|classes\.txt$|_annotations\.coco\.json$|README\.md$", f)][:4]:
            try:
                t = open(hf_hub_download(repo, f, repo_type="dataset")).read()
                print(f"--- {f}\n" + (t[:1800] if not f.endswith(".json") else
                      json.dumps([c.get("name") for c in json.loads(t).get("categories", [])])))
            except Exception as e:
                print(f, "ERR", e)
        pq = [f for f in files if f.endswith(".parquet")][:1]
        if pq:
            import pyarrow.parquet as p
            t = p.read_table(hf_hub_download(repo, pq[0], repo_type="dataset"))
            print("--- parquet schema", t.schema.to_string()[:1500], "rows", t.num_rows)
            row = t.slice(0, 1).to_pylist()[0]
            print({k: (str(v)[:300] if not isinstance(v, (bytes, dict)) or k != "image" else "<image>") for k, v in row.items()})
    except Exception as e:
        print(repo, "ERROR", e)


for r in ["aurora0403/Railway_Foreign_Object_Dataset", "ybli/yolo-railway-track-defect-object-detection",
          "crangana/railroad-fault-detection", "futureflsl/railway-dataset", "samyuktha01/Indian_Railway_maintance",
          "Akhila-9849/waste_littering", "Akhila-9849/trash_detection", "alexNova/MRS-Trash-Detection",
          "ToXiN0/Powerlines-detection", "sirlab-ai/railway-forest-daylight__63k3mlcn-preview", "SVR7/Railroad_crossings"]:
    hf(r)
info = api.dataset_info("EPDCL/pd-defect")
fs = [s.rfilename for s in info.siblings]
print("\n===== EPDCL lean/crossarm trees", sorted({"/".join(f.split("/")[:4]) for f in fs if f.startswith(("pole_lean", "crossarm"))})[:40])
for f in ["pole_lean_assessment/README.md"]:
    print(open(hf_hub_download("EPDCL/pd-defect", f, repo_type="dataset")).read()[:2500])
with urllib.request.urlopen("https://zenodo.org/records/7781388/files/labels.txt?download=1", timeout=60) as r:
    print("\n===== zenodo 7781388 labels.txt\n", r.read()[:1000].decode(errors="replace"))
try:
    from remotezip import RemoteZip
    for u in ["https://zenodo.org/records/14604384/files/composite_MPID-20250106T113900Z-001.zip?download=1",
              "https://zenodo.org/records/7781388/files/Annotations.zip?download=1"]:
        with RemoteZip(u) as z:
            names = z.namelist()
            print(f"\n===== zip {u.split('/')[-1][:50]} {len(names)} entries", names[:25])
            exts = {}
            for n in names:
                e = n.rsplit(".", 1)[-1].lower()
                exts[e] = exts.get(e, 0) + 1
            print(exts)
            xml = [n for n in names if n.endswith((".xml", ".txt", ".json"))][:1]
            if xml:
                print(z.read(xml[0])[:1200].decode(errors="replace"))
except Exception as e:
    print("remotezip ERROR", e)
