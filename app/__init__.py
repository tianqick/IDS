from flask import Flask
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db
from .models import ModelInfo
from .routes.api import api_bp
from .routes.frontend import frontend_bp
from .services.model_registry import dump_required_columns, get_active_model, set_active_model
from .services.traffic_monitor import traffic_monitor_service


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(frontend_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        ensure_default_model_metadata()
        if app.config["AUTO_START_TRAFFIC_MONITOR"]:
            traffic_monitor_service.start(app)

    return app


def ensure_schema_updates():
    inspector = inspect(db.engine)
    table_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in {"model_info", "detect_record", "detection_task"}
    }
    dialect = db.engine.dialect.name

    statements = []
    if "description" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN description TEXT")
    if "dataset_format" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN dataset_format TEXT")
    if "required_columns" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN required_columns TEXT")
    if "is_active" not in table_columns["model_info"]:
        if dialect == "sqlite":
            statements.append("ALTER TABLE model_info ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0")
        else:
            statements.append("ALTER TABLE model_info ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0")
    if "metric_precision" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_precision FLOAT DEFAULT 0")
    if "metric_recall" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_recall FLOAT DEFAULT 0")
    if "metric_f1_score" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_f1_score FLOAT DEFAULT 0")
    if "metric_fpr" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_fpr FLOAT DEFAULT 0")
    if "metric_fnr" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_fnr FLOAT DEFAULT 0")
    if "metric_inference_latency_ms" not in table_columns["model_info"]:
        statements.append("ALTER TABLE model_info ADD COLUMN metric_inference_latency_ms FLOAT DEFAULT 0")

    if "model_id" not in table_columns["detect_record"]:
        statements.append("ALTER TABLE detect_record ADD COLUMN model_id INTEGER")
    if "model_name" not in table_columns["detect_record"]:
        statements.append("ALTER TABLE detect_record ADD COLUMN model_name VARCHAR(100)")
    if "model_path" not in table_columns["detect_record"]:
        statements.append("ALTER TABLE detect_record ADD COLUMN model_path VARCHAR(255)")

    if "model_id" not in table_columns["detection_task"]:
        statements.append("ALTER TABLE detection_task ADD COLUMN model_id INTEGER")

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def ensure_default_model_metadata():
    default_required_columns = [
        "Flow ID",
        "Source IP",
        "Source Port",
        "Destination IP",
        "Destination Port",
        "Timestamp",
        "Label (optional for detection, used in training/evaluation)",
    ]
    default_dataset_format = (
        "CSV with CIC-IDS style traffic features and a header row. "
        "Training/evaluation data should include Label; detection uploads may omit Label."
    )
    default_model = ModelInfo.query.filter_by(model_path="1D_CNN_BiLSTM_Attn_best.pth").first()
    changed = False

    if default_model is None:
        default_model = ModelInfo(
            model_name="1D-CNN + BiLSTM + Attention",
            model_path="1D_CNN_BiLSTM_Attn_best.pth",
            model_type="Deep Learning",
            accuracy=0.996845,
            precision=0.996907,
            recall=0.996845,
            f1_score=0.996676,
            fpr=0.003212,
            fnr=0.003155,
            inference_latency_ms=0.00966,
            description="Default demo model",
            dataset_format=default_dataset_format,
            required_columns=dump_required_columns(default_required_columns),
            is_active=True,
        )
        db.session.add(default_model)
        changed = True
    else:
        expected_values = {
            "model_name": "1D-CNN + BiLSTM + Attention",
            "model_type": "Deep Learning",
            "accuracy": 0.996845,
            "precision": 0.996907,
            "recall": 0.996845,
            "f1_score": 0.996676,
            "fpr": 0.003212,
            "fnr": 0.003155,
            "inference_latency_ms": 0.00966,
            "description": "Default demo model",
            "dataset_format": default_dataset_format,
            "required_columns": dump_required_columns(default_required_columns),
        }
        for field, value in expected_values.items():
            if getattr(default_model, field) != value:
                setattr(default_model, field, value)
                changed = True

    if not get_active_model():
        set_active_model(default_model)
        changed = True

    if changed:
        db.session.commit()
