from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RVI_", env_file=".env")

    database_url: str = "sqlite:///./rvi.db"
    evidence_dir: Path = Path("./evidence")
    model_dir: Path = Path("./models")  # ohe_detector.onnx + ohe_detector.names.json (from ml/ohe)
    taxonomy_path: Path = REPO_ROOT / "shared" / "taxonomy.json"
    # Optional ONNX detector exported from ml/train (YOLO-format output). Absent in Beta by default.
    detector_onnx: Path | None = None
    detector_labels: Path | None = None
    detector_conf: float = 0.35
    # Image quality gate thresholds (tuned by ml/bench/bench_quality_gate.py)
    min_sharpness: float = 60.0      # variance of Laplacian on 1024-px long side
    min_brightness: float = 45.0     # mean luma 0..255
    max_brightness: float = 225.0
    max_clipped_fraction: float = 0.25  # share of pixels >= 253 (glare)
    # Sign-in (OHE service). 'header' trusts X-Actor/X-Role (development, tests); 'token' requires sign-in.
    auth_mode: str = "header"
    secret_key: str = "change-me"     # set RVI_SECRET_KEY in production
    token_hours: int = 12
    users_file: Path = Path("./users.yaml")
    # Optional web push for urgent findings (empty = alert feed only)
    alert_webhook: str = ""
    # Phone app updates: newest build served at /ohe/app/latest + /ohe/app/apk from this folder. Optionally kept in sync
    # with the GitHub pre-release that CI publishes (needs a read-only token for the private repository).
    app_dir: Path = Path("./app_releases")
    github_token: str = ""
    app_release_repo: str = "dhruvv2112-coder/railway-visual-inspection-beta"
    app_release_tag: str = "android-beta"


settings = Settings()
