import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
FACE_DIR = DATA_DIR / "faces"
DB_PATH = DATA_DIR / "app.db"
MODEL_PATH = DATA_DIR / "lbph_model.yml"
LABELS_PATH = DATA_DIR / "labels.json"

def env_path(name: str, default: str = "") -> Path:
    value = os.getenv(name, default).strip()
    if not value:
        return Path()
    path = Path(value).expanduser()
    return path if path.is_absolute() else BACKEND_DIR / path


CAMERA_URL = os.getenv("IPWEBCAM_URL", os.getenv("CAMERA_URL", "")).strip()
CAMERA_TIMEOUT_SECONDS = float(os.getenv("CAMERA_TIMEOUT_SECONDS", "5"))
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "70"))
FACE_MODEL_PROVIDER = os.getenv("FACE_MODEL_PROVIDER", "lbph").strip().lower()
FACE_MODEL_PATH = env_path("FACE_MODEL_PATH")
FACE_MODEL_LABELS_PATH = env_path("FACE_MODEL_LABELS_PATH")
FACE_MODEL_THRESHOLD = float(os.getenv("FACE_MODEL_THRESHOLD", "0.55"))

_size = os.getenv("FACE_MODEL_INPUT_SIZE", "224x224").lower().replace("x", " ").replace(",", " ").split()
try:
    FACE_MODEL_INPUT_SIZE = (int(_size[0]), int(_size[1]))
except (IndexError, ValueError):
    FACE_MODEL_INPUT_SIZE = (224, 224)

FOCUS_WEBHOOK_URL = os.getenv("FOCUS_WEBHOOK_URL", "")
FOCUS_SERIAL_PORT = os.getenv("FOCUS_SERIAL_PORT", "")
FOCUS_SERIAL_BAUDRATE = int(os.getenv("FOCUS_SERIAL_BAUDRATE", "9600"))
FOCUS_SERIAL_TEMPLATE = os.getenv("FOCUS_SERIAL_TEMPLATE", "ON {plate} {owner}\n")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FACE_DIR.mkdir(parents=True, exist_ok=True)
