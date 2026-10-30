from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RVI_", env_file=".env")

    database_url: str = "sqlite:///./rvi.db"
    evidence_dir: Path = Path("./evidence")
    taxonomy_path: Path = REPO_ROOT / "shared" / "taxonomy.json"
    # Optional ONNX detector exported from ml/train (YOLO-format output). Absent in Beta by default.
    detector_onnx: Path | None = None
    detector_labels: Path | None = None
    detector_conf: float = 0.35
    # Image quality gate thresholds (tuned by ml/bench/bench_quality_gate.py)
    min_sharpness: float = 60.0      # variance of Laplacian on 1024-px long side
    min_brightness: float = 45.0     # mean luma 0..255
    max_brightness: float = 225.0
    max_clipped_fraction: float = 0.25  # share of pixels at 0 or 255


settings = Settings()
