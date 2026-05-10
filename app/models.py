from datetime import datetime

from .extensions import db


class User(db.Model):
    __tablename__ = "user"
    __table_args__ = {"comment": "系统用户表"}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    detect_records = db.relationship("DetectRecord", backref="user", lazy=True)


class ModelInfo(db.Model):
    __tablename__ = "model_info"
    __table_args__ = {"comment": "模型信息表"}

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    model_path = db.Column(db.String(255), nullable=False)
    model_type = db.Column(db.String(50))
    accuracy = db.Column(db.Float, default=0.0)
    precision = db.Column("metric_precision", db.Float, default=0.0)
    recall = db.Column("metric_recall", db.Float, default=0.0)
    f1_score = db.Column("metric_f1_score", db.Float, default=0.0)
    fpr = db.Column("metric_fpr", db.Float, default=0.0)
    fnr = db.Column("metric_fnr", db.Float, default=0.0)
    inference_latency_ms = db.Column("metric_inference_latency_ms", db.Float, default=0.0)
    description = db.Column(db.Text)
    dataset_format = db.Column(db.Text)
    required_columns = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class DatasetInfo(db.Model):
    __tablename__ = "dataset_info"
    __table_args__ = {"comment": "数据集信息表"}

    id = db.Column(db.Integer, primary_key=True)
    dataset_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    sample_count = db.Column(db.Integer, default=0)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)


class DetectRecord(db.Model):
    __tablename__ = "detect_record"
    __table_args__ = {"comment": "检测记录表"}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source_file = db.Column(db.String(255))
    model_id = db.Column(db.Integer)
    model_name = db.Column(db.String(100))
    model_path = db.Column(db.String(255))
    sample_count = db.Column(db.Integer, default=0)
    normal_count = db.Column(db.Integer, default=0)
    attack_count = db.Column(db.Integer, default=0)
    detect_time = db.Column(db.DateTime, default=datetime.utcnow)

    attack_results = db.relationship("AttackResult", backref="record", lazy=True)
    alarm_logs = db.relationship("AlarmLog", backref="record", lazy=True)
    tasks = db.relationship("DetectionTask", backref="record", lazy=True)


class AttackResult(db.Model):
    __tablename__ = "attack_result"
    __table_args__ = {"comment": "攻击结果表"}

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer, db.ForeignKey("detect_record.id"), nullable=False
    )
    attack_type = db.Column(db.String(50), nullable=False)
    risk_level = db.Column(db.String(20), default="low")
    confidence = db.Column(db.Float, default=0.0)
    src_ip = db.Column(db.String(50))
    dst_ip = db.Column(db.String(50))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class AlarmLog(db.Model):
    __tablename__ = "alarm_log"
    __table_args__ = {"comment": "告警日志表"}

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer, db.ForeignKey("detect_record.id"), nullable=False
    )
    alarm_content = db.Column(db.String(255), nullable=False)
    alarm_level = db.Column(db.String(20), default="medium")
    status = db.Column(db.String(20), default="unprocessed")
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class OperationLog(db.Model):
    __tablename__ = "operation_log"
    __table_args__ = {"comment": "操作日志表"}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.String(255))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class DetectionTask(db.Model):
    __tablename__ = "detection_task"
    __table_args__ = {"comment": "检测任务表"}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    record_id = db.Column(db.Integer, db.ForeignKey("detect_record.id"), nullable=True)
    model_id = db.Column(db.Integer, nullable=True)
    source_file = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    total_rows = db.Column(db.Integer, default=0)
    processed_rows = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="queued", nullable=False)
    message = db.Column(db.String(255), default="Task queued")
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = db.relationship("User", backref="detection_tasks", lazy=True)
