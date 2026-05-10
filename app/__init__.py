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
    table_comments = {
        "user": "系统用户表",
        "model_info": "模型信息表",
        "dataset_info": "数据集信息表",
        "detect_record": "检测记录表",
        "attack_result": "攻击结果表",
        "alarm_log": "告警日志表",
        "operation_log": "操作日志表",
        "detection_task": "检测任务表",
    }

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

    if dialect == "mysql":
        for table_name, comment in table_comments.items():
            statements.append(f"ALTER TABLE {table_name} COMMENT = '{comment}'")

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def ensure_default_model_metadata():
    default_required_columns = [
        "Flow ID",
        "Src IP",
        "Src Port",
        "Dst IP",
        "Dst Port",
        "Protocol",
        "Timestamp",
        "Flow Duration",
        "Total Fwd Packet",
        "Total Bwd packets",
        "Total Length of Fwd Packet",
        "Total Length of Bwd Packet",
        "Fwd Packet Length Max",
        "Fwd Packet Length Min",
        "Fwd Packet Length Mean",
        "Fwd Packet Length Std",
        "Bwd Packet Length Max",
        "Bwd Packet Length Min",
        "Bwd Packet Length Mean",
        "Bwd Packet Length Std",
        "Flow Bytes/s",
        "Flow Packets/s",
        "Flow IAT Mean",
        "Flow IAT Std",
        "Flow IAT Max",
        "Flow IAT Min",
        "Fwd IAT Total",
        "Fwd IAT Mean",
        "Fwd IAT Std",
        "Fwd IAT Max",
        "Fwd IAT Min",
        "Bwd IAT Total",
        "Bwd IAT Mean",
        "Bwd IAT Std",
        "Bwd IAT Max",
        "Bwd IAT Min",
        "Fwd PSH Flags",
        "Bwd PSH Flags",
        "Fwd URG Flags",
        "Bwd URG Flags",
        "Fwd Header Length",
        "Bwd Header Length",
        "Fwd Packets/s",
        "Bwd Packets/s",
        "Packet Length Min",
        "Packet Length Max",
        "Packet Length Mean",
        "Packet Length Std",
        "Packet Length Variance",
        "FIN Flag Count",
        "SYN Flag Count",
        "RST Flag Count",
        "PSH Flag Count",
        "ACK Flag Count",
        "URG Flag Count",
        "CWR Flag Count",
        "ECE Flag Count",
        "Down/Up Ratio",
        "Average Packet Size",
        "Fwd Segment Size Avg",
        "Bwd Segment Size Avg",
        "Fwd Bytes/Bulk Avg",
        "Fwd Packet/Bulk Avg",
        "Fwd Bulk Rate Avg",
        "Bwd Bytes/Bulk Avg",
        "Bwd Packet/Bulk Avg",
        "Bwd Bulk Rate Avg",
        "Subflow Fwd Packets",
        "Subflow Fwd Bytes",
        "Subflow Bwd Packets",
        "Subflow Bwd Bytes",
        "FWD Init Win Bytes",
        "Bwd Init Win Bytes",
        "Fwd Act Data Pkts",
        "Fwd Seg Size Min",
        "Active Mean",
        "Active Std",
        "Active Max",
        "Active Min",
        "Idle Mean",
        "Idle Std",
        "Idle Max",
        "Idle Min",
        "Label (required for training/evaluation, optional for detection)",
    ]
    default_dataset_format = (
        "CSV exported from CIC-IDS2017 / CICFlowMeter with the original header row. "
        "Training and evaluation data must include the Label column; online detection uploads may omit Label, "
        "but the remaining feature columns should keep the original CIC-IDS2017 names and order."
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
