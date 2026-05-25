import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ["DATABASE_URI"] = "sqlite:///screenshot_demo.db"
os.environ["FLASK_RUN_HOST"] = "127.0.0.1"
os.environ["FLASK_RUN_PORT"] = "5055"

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)
