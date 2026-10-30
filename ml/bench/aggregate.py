"""Combine all reports/*.json into reports/BENCHMARK_REPORT.md (industry benchmarking summary)."""
import json

from common import REPORTS, md_table

ORDER = ["quality_gate", "ocr_markers", "asr", "translation", "detector", "dedup"]


def main():
    parts = ["# RVI Beta – Model Benchmark Report\n",
             "All numbers produced by `ml/bench/*` in CI. Each section lists its data source, environment and failures.\n"]
    for name in ORDER:
        p = REPORTS / f"{name}.json"
        if not p.exists():
            parts.append(f"\n## {name}\n\n_Not run or failed before writing results._\n")
            continue
        d = json.loads(p.read_text())
        parts.append(f"\n## {d['title']}\n\n{d['summary']}\n\n" + md_table(d["results"]))
        for n in d.get("notes", []):
            parts.append(f"- {n}\n")
        parts.append(f"\n_Environment_: {d['environment'].get('runner')} · {d['environment'].get('cpu_count')} CPU · "
                     f"torch {d['environment'].get('torch', 'n/a')} · {d['environment']['timestamp_utc']}\n")
    (REPORTS / "BENCHMARK_REPORT.md").write_text("".join(parts))
    print("".join(parts))


if __name__ == "__main__":
    main()
