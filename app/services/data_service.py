from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from flask import current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import AlarmLog, AttackResult, DatasetInfo, DetectRecord, OperationLog
from .model_service import ModelService
from .model_registry import get_model_for_detection


ALLOWED_EXTENSIONS = {"csv"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_dataset(file_storage) -> tuple[str, int]:
    Path(current_app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{secure_filename(file_storage.filename)}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)

    sample_count = count_csv_rows(path)
    db.session.add(
        DatasetInfo(
            dataset_name=file_storage.filename,
            file_path=path,
            sample_count=sample_count,
        )
    )
    db.session.commit()
    return path, sample_count


def count_csv_rows(file_path: str) -> int:
    with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        return max(sum(1 for _ in csv.reader(csv_file)) - 1, 0)


def run_detection(
    file_path: str,
    user_id: int,
    username: str,
    model_id: int | None = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> DetectRecord:
    resolved_model_id, model_name, model_path_display, model_path = get_model_for_detection(model_id)
    service = ModelService(model_path)
    record = DetectRecord(
        user_id=user_id,
        source_file=os.path.basename(file_path),
        model_id=resolved_model_id,
        model_name=model_name,
        model_path=model_path_display,
        sample_count=0,
        normal_count=0,
        attack_count=0,
    )
    db.session.add(record)
    db.session.flush()

    db.session.commit()

    total_samples = 0
    total_normals = 0
    total_attacks = 0
    result_buffer = []
    alarm_buffer = []
    db_batch_size = current_app.config["DB_BATCH_SIZE"]

    for predictions in service.predict_file_in_chunks(file_path):
        for item in predictions:
            total_samples += 1
            is_benign = item.attack_type == "BENIGN"
            total_normals += 1 if is_benign else 0
            total_attacks += 0 if is_benign else 1
            result_buffer.append(
                {
                    "record_id": record.id,
                    "attack_type": item.attack_type,
                    "risk_level": item.risk_level,
                    "confidence": item.confidence,
                    "src_ip": item.src_ip,
                    "dst_ip": item.dst_ip,
                }
            )
            if not is_benign:
                alarm_buffer.append(
                    {
                        "record_id": record.id,
                        "alarm_content": f"Detected {item.attack_type} attack from {item.src_ip}",
                        "alarm_level": item.risk_level,
                    }
                )

        _flush_detection_buffers(result_buffer, alarm_buffer, db_batch_size)
        if progress_callback:
            progress_callback(total_samples)

    _flush_detection_buffers(result_buffer, alarm_buffer, 1)

    record = DetectRecord.query.get(record.id)
    record.sample_count = total_samples
    record.normal_count = total_normals
    record.attack_count = total_attacks

    db.session.add(
        OperationLog(
            username=username,
            action="run_detection",
            detail=f"Detected file {os.path.basename(file_path)} with model {model_name}",
        )
    )
    db.session.commit()
    return record


def _flush_detection_buffers(result_buffer, alarm_buffer, batch_threshold: int) -> None:
    wrote_data = False
    if len(result_buffer) >= batch_threshold:
        db.session.bulk_insert_mappings(AttackResult, result_buffer)
        result_buffer.clear()
        wrote_data = True
    if len(alarm_buffer) >= batch_threshold:
        db.session.bulk_insert_mappings(AlarmLog, alarm_buffer)
        alarm_buffer.clear()
        wrote_data = True
    if wrote_data:
        db.session.commit()


def build_dashboard_stats(current_user_id: Optional[int] = None, role: str = "admin") -> Dict[str, object]:
    from ..models import AlarmLog, AttackResult, DatasetInfo, DetectRecord, User

    records_query = DetectRecord.query
    results_query = AttackResult.query
    alarms_query = AlarmLog.query

    if role != "admin" and current_user_id is not None:
        records_query = records_query.filter(DetectRecord.user_id == current_user_id)
        results_query = results_query.join(DetectRecord).filter(DetectRecord.user_id == current_user_id)
        alarms_query = alarms_query.join(DetectRecord).filter(DetectRecord.user_id == current_user_id)

    recent_records = records_query.order_by(DetectRecord.detect_time.desc()).limit(7).all()
    latest_records = recent_records[:5]
    alarms = alarms_query.order_by(AlarmLog.create_time.desc()).limit(5).all()
    alarm_count = alarms_query.count()
    record_count = records_query.count()

    attack_distribution_rows = (
        results_query.with_entities(AttackResult.attack_type, func.count(AttackResult.id))
        .group_by(AttackResult.attack_type)
        .all()
    )
    attack_distribution = {attack_type: count for attack_type, count in attack_distribution_rows}
    trend = {}
    for record in recent_records:
        day_label = record.detect_time.strftime("%m-%d")
        trend.setdefault(day_label, 0)
        trend[day_label] += record.attack_count

    return {
        "user_count": User.query.count() if role == "admin" else 1,
        "dataset_count": DatasetInfo.query.count(),
        "record_count": record_count,
        "alarm_count": alarm_count if role != "admin" else AlarmLog.query.count(),
        "attack_distribution": attack_distribution,
        "trend_labels": list(reversed(list(trend.keys()))),
        "trend_values": list(reversed(list(trend.values()))),
        "recent_alarms": [serialize_alarm_brief(item) for item in alarms],
        "recent_records": [serialize_record_brief(item) for item in latest_records],
    }


def serialize_alarm_brief(item: AlarmLog) -> Dict[str, object]:
    return {
        "id": item.id,
        "record_id": item.record_id,
        "alarm_content": item.alarm_content,
        "alarm_level": item.alarm_level,
        "status": item.status,
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_record_brief(item: DetectRecord) -> Dict[str, object]:
    return {
        "id": item.id,
        "source_file": item.source_file,
        "sample_count": item.sample_count,
        "attack_count": item.attack_count,
        "detect_time": item.detect_time.strftime("%Y-%m-%d %H:%M:%S"),
    }
