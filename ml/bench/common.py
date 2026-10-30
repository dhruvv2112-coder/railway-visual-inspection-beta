"""Shared helpers for benchmarks: report writing, timing, environment capture.
Every benchmark writes reports/<name>.json and reports/<name>.md with identical numbers."""
import json
import os
import platform
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPORTS = Path(os.environ.get("RVI_REPORTS", Path(__file__).resolve().parents[2] / "reports"))
DATA = Path(os.environ.get("RVI_DATA", Path(__file__).resolve().parents[2] / "ml" / "data" / "cache"))
REPORTS.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)


def env() -> dict:
    info = {"python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "runner": os.environ.get("RUNNER_NAME", "local"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info


@contextmanager
def timer(store: dict, key: str):
    t = time.perf_counter()
    yield
    store[key] = round(time.perf_counter() - t, 4)


def md_table(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return "_no rows_\n"
    cols = cols or list(rows[0].keys())
    fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join(fmt(r.get(c, "")) for c in cols) + " |\n"
    return out


def write_report(name: str, title: str, summary: str, results: list[dict], extra: dict | None = None,
                 cols: list[str] | None = None, notes: list[str] | None = None) -> Path:
    payload = {"name": name, "title": title, "summary": summary, "environment": env(), "results": results,
               "extra": extra or {}, "notes": notes or []}
    (REPORTS / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str))
    md = f"# {title}\n\n{summary}\n\n" + md_table(results, cols)
    if notes:
        md += "\n**Notes**\n\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    md += f"\n_Environment_: `{json.dumps(payload['environment'])}`\n"
    (REPORTS / f"{name}.md").write_text(md)
    print(md)
    return REPORTS / f"{name}.json"
