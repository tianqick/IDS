import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_MODEL_PATH = (
    BASE_DIR / "1D_CNN_BiLSTM_Attn_best.pth"
    if (BASE_DIR / "1D_CNN_BiLSTM_Attn_best.pth").exists()
    else BASE_DIR / "best_hybrid_ids_model.pth"
)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "ids-system-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "mysql+pymysql://root:123456@127.0.0.1:3306/ids_system?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MODEL_UPLOAD_FOLDER = str(BASE_DIR / "uploads" / "models")
    LOG_FOLDER = str(BASE_DIR / "logs")
    MODEL_PATH = os.getenv(
        "MODEL_PATH", str(DEFAULT_MODEL_PATH)
    )
    DATASET_DIR = os.getenv("DATASET_DIR", str(BASE_DIR / "dataset"))
    ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", str(BASE_DIR / "artifacts"))
    TRAFFIC_FLOW_INPUT_DIR = os.getenv("TRAFFIC_FLOW_INPUT_DIR", str(BASE_DIR / "uploads" / "traffic_flows" / "inbox"))
    TRAFFIC_FLOW_ARCHIVE_DIR = os.getenv("TRAFFIC_FLOW_ARCHIVE_DIR", str(BASE_DIR / "uploads" / "traffic_flows" / "archive"))
    TRAFFIC_PCAP_DIR = os.getenv("TRAFFIC_PCAP_DIR", str(BASE_DIR / "uploads" / "traffic_flows" / "pcap"))
    TRAFFIC_PCAP_ARCHIVE_DIR = os.getenv("TRAFFIC_PCAP_ARCHIVE_DIR", str(BASE_DIR / "uploads" / "traffic_flows" / "pcap_archive"))
    TRAFFIC_MONITOR_INTERVAL = int(os.getenv("TRAFFIC_MONITOR_INTERVAL", "10"))
    AUTO_START_TRAFFIC_MONITOR = os.getenv("AUTO_START_TRAFFIC_MONITOR", "false").lower() == "true"
    TSHARK_PATH = os.getenv("TSHARK_PATH", "")
    TRAFFIC_CAPTURE_INTERFACE = os.getenv("TRAFFIC_CAPTURE_INTERFACE", "")
    TRAFFIC_CAPTURE_DURATION = int(os.getenv("TRAFFIC_CAPTURE_DURATION", "15"))
    TRAFFIC_CAPTURE_FILTER = os.getenv("TRAFFIC_CAPTURE_FILTER", "")
    MODEL_INPUT_SIZE = int(os.getenv("MODEL_INPUT_SIZE", "32"))
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024
    PREDICT_CHUNK_SIZE = int(os.getenv("PREDICT_CHUNK_SIZE", "5000"))
    INFERENCE_BATCH_SIZE = int(os.getenv("INFERENCE_BATCH_SIZE", "1024"))
    DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "2000"))
