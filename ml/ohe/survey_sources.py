"""Dataset survey for the OHE classes still missing (run in CI, which can reach HF / Zenodo / figshare / GitHub).
Searches each platform one keyword at a time, lists files, licences and class names of the hits, and writes
reports/ohe_dataset_survey.json. It downloads nothing large: metadata, file lists and small yaml/json/README only."""
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(os.environ.get("RVI_REPORTS", "reports")) / "ohe_dataset_survey.json"
KEYWORDS = ["bird nest", "nest", "catenary", "overhead line", "pantograph", "dropper", "insulator", "power line",
            "powerline", "transmission line", "utility pole", "electric pole", "pole", "corrosion", "rust",
            "foreign object", "railway", "vegetation encroachment", "cross arm", "EPDCL"]
HF_EXTRA = ["EPDCL/pd-defect", "EPDCL/Electrical-Lines-Defect-Detection"]
GH_RELEASES = ["andreluizbvs/PLAD", "phd-benel/BGI", "phd-benel/VPMBGI", "phd-benel/MPID"]
FIGSHARE = [24180738]  # RailFOD23
ZENODO_RECORDS = [4015912, 8078800]  # bird nest supplementary files; unknown
ZENODO_Q = ["bird nest power line", "catenary", "railway overhead", "insulator defect", "power line inspection images"]
CKAN = ["https://data.fid-move.de/api/3/action/package_search?q=osdar23"]
RELEVANT = re.compile(r"nest|catenar|overhead|pantograph|dropper|insulat|power.?line|transmission|pole|corros|rust|"
                      r"foreign|rail|cross.?arm|epdcl|vegetation|tower", re.I)


def get(url, binary=False, limit=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "rvi-survey/1.0",
                                               **({"Authorization": f"Bearer {os.environ['GH_TOKEN']}"}
                                                  if "api.github.com" in url and os.environ.get("GH_TOKEN") else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read(limit)
    return b if binary else json.loads(b) if b[:1] in (b"{", b"[") else b.decode("utf-8", "replace")


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # record and keep surveying
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}


def hf():
    from huggingface_hub import HfApi
    api, seen, hits = HfApi(), set(), []
    for k in KEYWORDS:
        for d in api.list_datasets(search=k, limit=40):
            if d.id in seen or not RELEVANT.search(d.id):
                continue
            seen.add(d.id)
            hits.append({"id": d.id, "keyword": k, "downloads": getattr(d, "downloads", None),
                         "licence": [t for t in (d.tags or []) if t.startswith("license:")]})
    for d in api.list_datasets(author="EPDCL"):
        if d.id not in seen:
            seen.add(d.id)
            hits.append({"id": d.id, "keyword": "author:EPDCL", "licence": [t for t in (d.tags or []) if t.startswith("license:")]})
    for h in hits:
        h.update(safe(hf_detail, api, h["id"]))
    for x in HF_EXTRA:
        if x not in seen:
            hits.append({"id": x, "keyword": "direct", **safe(hf_detail, api, x)})
    return hits


def hf_detail(api, rid):
    from huggingface_hub import hf_hub_download
    files = api.list_repo_files(rid, repo_type="dataset")
    exts = {}
    for f in files:
        e = f.rsplit(".", 1)[-1].lower() if "." in f else ""
        exts[e] = exts.get(e, 0) + 1
    top = sorted({f.split("/")[0] for f in files})
    small = [f for f in files if re.search(r"(data\.yaml|README\.md|dataset_info\.json|classes\.txt)$", f, re.I)][:12]
    meta = {}
    for f in small:
        try:
            meta[f] = Path(hf_hub_download(rid, f, repo_type="dataset")).read_text(errors="replace")[:1500]
        except Exception as e:
            meta[f] = f"error {e}"[:200]
    return {"n_files": len(files), "exts": exts, "top_level": top[:40], "meta": meta}


def zenodo():
    out = [{"record": r, **safe(lambda r=r: zen_rec(get(f"https://zenodo.org/api/records/{r}")))} for r in ZENODO_RECORDS]
    for q in ZENODO_Q:
        res = safe(get, "https://zenodo.org/api/records?size=15&q=" + urllib.parse.quote(q))
        for h in (res.get("hits", {}).get("hits", []) if isinstance(res, dict) else []):
            if h.get("metadata", {}).get("resource_type", {}).get("type") in ("dataset", "image", None):
                out.append({"query": q, **zen_rec(h)})
    return out


def zen_rec(h):
    m = h.get("metadata", {})
    return {"id": h.get("id"), "title": m.get("title"), "type": m.get("resource_type", {}).get("type"),
            "licence": (m.get("license") or {}).get("id"), "access": m.get("access_right"),
            "files": [(f.get("key"), round(f.get("size", 0) / 1e6, 1)) for f in h.get("files", [])][:20],
            "description": re.sub("<[^>]+>", " ", m.get("description", ""))[:600]}


def figshare():
    out = []
    for a in FIGSHARE:
        r = safe(get, f"https://api.figshare.com/v2/articles/{a}")
        out.append({"article": a, "title": r.get("title"), "licence": (r.get("license") or {}).get("name"),
                    "files": [(f["name"], round(f["size"] / 1e6, 1), f["download_url"]) for f in r.get("files", [])],
                    "description": re.sub("<[^>]+>", " ", r.get("description", ""))[:800]} if "error" not in r else r)
    return out


def gh_releases():
    out = []
    for repo in GH_RELEASES:
        r = safe(get, f"https://api.github.com/repos/{repo}/releases")
        out.append({"repo": repo, "assets": [(a["name"], round(a["size"] / 1e6, 1), a["browser_download_url"])
                                             for rel in r for a in rel.get("assets", [])] if isinstance(r, list) else r})
    return out


def ckan():
    out = []
    for u in CKAN:
        r = safe(get, u)
        for p in (r.get("result", {}).get("results", []) if isinstance(r, dict) else []):
            out.append({"name": p.get("name"), "title": p.get("title"), "licence": p.get("license_id"),
                        "resources": [(x.get("name"), x.get("format"), x.get("size"), x.get("url")) for x in p.get("resources", [])][:60]})
        if not out:
            out.append(r)
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rep = {}
    for name, fn in (("huggingface", hf), ("zenodo", zenodo), ("figshare", figshare), ("github_releases", gh_releases),
                     ("fid_move_osdar23", ckan)):
        rep[name] = safe(fn)
        print(name, json.dumps(rep[name])[:3000], flush=True)
    OUT.write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
