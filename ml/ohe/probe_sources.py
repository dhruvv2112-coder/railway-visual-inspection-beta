"""Print what new candidate datasets contain (files, classes, licences) so loaders can be written (run in CI)."""
import json
import re
import urllib.request

from huggingface_hub import HfApi, hf_hub_download

api = HfApi()


def show(title, obj):
    print(f"\n===== {title}\n{json.dumps(obj, indent=1, default=str)[:4000]}", flush=True)


def zen(rec):
    with urllib.request.urlopen(f"https://zenodo.org/api/records/{rec}", timeout=60) as r:
        d = json.load(r)
    show(f"zenodo {rec}: {d['metadata']['title']}", {"license": d["metadata"].get("license"),
         "files": [(f["key"], round(f["size"] / 1e6)) for f in d.get("files", [])]})


def hf(repo, readme=True):
    try:
        info = api.dataset_info(repo, files_metadata=False)
        files = [s.rfilename for s in info.siblings]
        dirs = sorted({"/".join(f.split("/")[:2]) for f in files})
        show(f"hf {repo}", {"license": (info.card_data or {}).get("license") if info.card_data else None,
                            "n_files": len(files), "dirs": dirs[:80],
                            "yaml_json": [f for f in files if re.search(r"(data\.ya?ml|classes|names|_annotations|\.json)$", f)][:40]})
        for f in [f for f in files if re.search(r"(^|/)data\.ya?ml$", f)][:3]:
            print(open(hf_hub_download(repo, f, repo_type="dataset")).read()[:1500])
        if readme and "README.md" in files:
            print(open(hf_hub_download(repo, "README.md", repo_type="dataset")).read()[:2500])
    except Exception as e:
        print(repo, "ERROR", e)


for rec in ("14604384", "4015912", "7781388"):
    try:
        zen(rec)
    except Exception as e:
        print(rec, "ERROR", e)
hf("ToXiN0/Powerlines-detection")
hf("EPDCL/pd-defect", readme=True)
for q in ("railway", "railroad", "catenary", "train track", "rail track", "indian railway", "power line", "insulator",
          "bird nest", "utility pole", "debris", "litter", "trash detection", "foreign object", "rock detection"):
    try:
        res = [(d.id, (d.card_data or {}).get("license") if getattr(d, "card_data", None) else None, d.downloads)
               for d in api.list_datasets(search=q, limit=40, full=True)]
        show(f"hf search '{q}'", res)
    except Exception as e:
        print(q, "ERROR", e)
