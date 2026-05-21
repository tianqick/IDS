from __future__ import annotations

from functools import wraps
import ipaddress
import socket
import threading
from pathlib import Path
from sqlalchemy import func
from werkzeug.utils import secure_filename

from flask import Blueprint, current_app, jsonify, request, session

from ..extensions import db
from ..models import AlarmLog, AttackResult, DetectRecord, DetectionTask, ModelInfo, OperationLog, User
from ..security import hash_password, is_password_hashed, verify_password
from ..services.data_service import allowed_file, build_dashboard_stats, run_detection, save_dataset
from ..services.model_registry import (
    dump_required_columns,
    get_active_model,
    get_model_for_detection,
    parse_required_columns,
    resolve_model_path,
    set_active_model,
)
from ..services.traffic_monitor import traffic_monitor_service


api_bp = Blueprint("api", __name__, url_prefix="/api")

DEFAULT_MODEL_REQUIRED_COLUMNS = [
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
DEFAULT_MODEL_DATASET_FORMAT = (
    "CSV exported from CIC-IDS2017 / CICFlowMeter with the original header row. "
    "Training and evaluation data must include the Label column; online detection uploads may omit Label, "
    "but the remaining feature columns should keep the original CIC-IDS2017 names and order."
)


def json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "message": message}), status


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return json_error("请先登录。", 401)
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if session.get("role") != "admin":
            return json_error("当前账号无管理员权限。", 403)
        return view(*args, **kwargs)

    return wrapped_view


def current_user_filters(query, model):
    if session.get("role") == "admin":
        return query
    if model is DetectRecord:
        return query.filter(DetectRecord.user_id == session["user_id"])
    if model is AttackResult:
        return query.join(DetectRecord).filter(DetectRecord.user_id == session["user_id"])
    if model is AlarmLog:
        return query.join(DetectRecord).filter(DetectRecord.user_id == session["user_id"])
    if model is DetectionTask:
        return query.filter(DetectionTask.user_id == session["user_id"])
    return query


def serialize_record(record: DetectRecord):
    alarm_count = AlarmLog.query.filter_by(record_id=record.id).count()
    return {
        "id": record.id,
        "user_id": record.user_id,
        "source_file": record.source_file,
        "model_id": record.model_id,
        "model_name": record.model_name,
        "model_path": record.model_path,
        "sample_count": record.sample_count,
        "normal_count": record.normal_count,
        "attack_count": record.attack_count,
        "detect_time": record.detect_time.strftime("%Y-%m-%d %H:%M:%S"),
        "alarm_count": alarm_count,
        "operator": record.user.username if record.user else f"user#{record.user_id}",
        "status": "存在告警" if alarm_count else "正常完成",
    }


def serialize_attack_result(item: AttackResult):
    return {
        "id": item.id,
        "record_id": item.record_id,
        "attack_type": item.attack_type,
        "risk_level": item.risk_level,
        "confidence": round(item.confidence, 4),
        "src_ip": item.src_ip,
        "dst_ip": item.dst_ip,
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_alarm(item: AlarmLog):
    return {
        "id": item.id,
        "record_id": item.record_id,
        "alarm_content": item.alarm_content,
        "alarm_level": item.alarm_level,
        "status": item.status,
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_model(item: ModelInfo):
    return {
        "id": item.id,
        "model_name": item.model_name,
        "model_path": item.model_path,
        "model_type": item.model_type,
        "accuracy": item.accuracy or 0.0,
        "precision": item.precision or 0.0,
        "recall": item.recall or 0.0,
        "f1_score": item.f1_score or 0.0,
        "fpr": item.fpr or 0.0,
        "fnr": item.fnr or 0.0,
        "inference_latency_ms": item.inference_latency_ms or 0.0,
        "description": item.description or "",
        "dataset_format": item.dataset_format or "",
        "required_columns": parse_required_columns(item.required_columns),
        "is_active": bool(item.is_active),
        "create_time": item.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_user(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "create_time": user.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_task(task: DetectionTask):
    progress = 0
    if task.total_rows:
        progress = min(100, int(task.processed_rows * 100 / task.total_rows))
    return {
        "id": task.id,
        "user_id": task.user_id,
        "record_id": task.record_id,
        "model_id": task.model_id,
        "source_file": task.source_file,
        "total_rows": task.total_rows,
        "processed_rows": task.processed_rows,
        "status": task.status,
        "message": task.message,
        "progress": progress,
        "create_time": task.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        "update_time": task.update_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def serialize_server_access() -> dict:
    host_header = request.host or "127.0.0.1:5000"
    if ":" in host_header:
        _, port = host_header.rsplit(":", 1)
    else:
        port = "5000"

    candidates = []
    seen = set()
    for host in ("127.0.0.1", "localhost"):
        url = f"http://{host}:{port}"
        if url not in seen:
            seen.add(url)
            candidates.append({"label": host, "url": url, "type": "local"})

    try:
        hostnames = {socket.gethostname(), socket.getfqdn()}
        for hostname in hostnames:
            for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, socket.AF_INET):
                if family != socket.AF_INET:
                    continue
                ip = sockaddr[0]
                try:
                    ip_obj = ipaddress.ip_address(ip)
                except ValueError:
                    continue
                if ip_obj.is_loopback or ip_obj.is_link_local or not ip_obj.is_private:
                    continue
                url = f"http://{ip}:{port}"
                if url in seen:
                    continue
                seen.add(url)
                candidates.append({"label": ip, "url": url, "type": "lan"})
    except socket.gaierror:
        pass

    return {
        "port": int(port),
        "items": candidates,
        "recommended_url": next((item["url"] for item in candidates if item["type"] == "lan"), candidates[0]["url"]),
    }


def build_traffic_monitor_payload(app):
    active_model = get_active_model()
    status = traffic_monitor_service.status(app)
    status["active_model"] = serialize_model(active_model) if active_model else None
    return status


def _run_detection_task(app, task_id: int, user_id: int, username: str):
    with app.app_context():
        task = DetectionTask.query.get(task_id)
        if not task:
            return
        task.status = "running"
        task.message = "任务执行中"
        db.session.commit()

        try:
            def on_progress(processed_rows: int):
                task_inner = DetectionTask.query.get(task_id)
                if not task_inner:
                    return
                task_inner.processed_rows = processed_rows
                task_inner.message = f"已处理 {processed_rows}/{task_inner.total_rows or 0} 行"
                db.session.commit()

            record = run_detection(
                task.file_path,
                user_id,
                username,
                model_id=task.model_id,
                progress_callback=on_progress,
            )
            task = DetectionTask.query.get(task_id)
            if task:
                task.record_id = record.id
                task.processed_rows = task.total_rows
                task.status = "completed"
                task.message = "检测完成"
                db.session.add(
                    OperationLog(
                        username=username,
                        action="complete_task",
                        detail=f"Completed detection task #{task.id}",
                    )
                )
                db.session.commit()
        except Exception as exc:  # pragma: no cover
            task = DetectionTask.query.get(task_id)
            if task:
                task.status = "failed"
                task.message = f"任务失败: {exc}"
                db.session.add(
                    OperationLog(
                        username=username,
                        action="fail_task",
                        detail=f"Detection task #{task.id} failed: {exc}",
                    )
                )
                db.session.commit()


@api_bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        return json_error("请输入用户名和密码。")

    user = User.query.filter_by(username=username).first()
    if not user or not verify_password(user.password, password):
        return json_error("用户名或密码错误。", 401)

    if not is_password_hashed(user.password):
        user.password = hash_password(password)

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    db.session.add(OperationLog(username=user.username, action="login", detail="User logged in"))
    db.session.commit()
    return jsonify({"ok": True, "user": serialize_user(user)})


@api_bp.post("/auth/logout")
@login_required
def logout():
    username = session.get("username", "unknown")
    db.session.add(OperationLog(username=username, action="logout", detail="User logged out"))
    db.session.commit()
    session.clear()
    return jsonify({"ok": True})


@api_bp.get("/auth/me")
def me():
    if "user_id" not in session:
        return jsonify({"ok": True, "authenticated": False, "user": None, "server_access": serialize_server_access()})
    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        return jsonify({"ok": True, "authenticated": False, "user": None, "server_access": serialize_server_access()})
    return jsonify({"ok": True, "authenticated": True, "user": serialize_user(user), "server_access": serialize_server_access()})


@api_bp.post("/auth/init-demo")
def init_demo():
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        db.session.add(User(username="admin", password=hash_password("admin123"), role="admin"))
    elif not is_password_hashed(admin.password):
        admin.password = hash_password("admin123")

    if not User.query.filter_by(username="user").first():
        db.session.add(User(username="user", password=hash_password("user123"), role="user"))

    if not ModelInfo.query.filter_by(model_path="1D_CNN_BiLSTM_Attn_best.pth").first():
        demo_model = ModelInfo(
            model_name="1D-CNN + BiLSTM + Attention",
            model_path="1D_CNN_BiLSTM_Attn_best.pth",
            model_type="PyTorch",
            accuracy=96.50,
            description="Default demo model",
            dataset_format=DEFAULT_MODEL_DATASET_FORMAT,
            required_columns=dump_required_columns(DEFAULT_MODEL_REQUIRED_COLUMNS),
            is_active=True,
        )
        db.session.add(demo_model)
    elif not get_active_model():
        demo_model = ModelInfo.query.filter_by(model_path="1D_CNN_BiLSTM_Attn_best.pth").first()
        if demo_model:
            set_active_model(demo_model)

    db.session.commit()
    return jsonify({"ok": True, "message": "演示账号已初始化。"})


@api_bp.get("/dashboard")
@login_required
def dashboard():
    stats = build_dashboard_stats(current_user_id=session["user_id"], role=session["role"])
    return jsonify({"ok": True, "data": stats})


@api_bp.post("/detect/upload")
@login_required
def upload_detection():
    file = request.files.get("dataset")
    model_id = request.form.get("model_id", type=int)
    if not file or not file.filename:
        return json_error("请先选择 CSV 文件。")
    if not allowed_file(file.filename):
        return json_error("当前仅支持 CSV 文件上传。")

    resolved_model_id, model_name, _, _ = get_model_for_detection(model_id)
    file_path, sample_count = save_dataset(file)
    task = DetectionTask(
        user_id=session["user_id"],
        model_id=resolved_model_id,
        source_file=file.filename,
        file_path=file_path,
        total_rows=sample_count,
        processed_rows=0,
        status="queued",
        message=f"Task queued for model {model_name}",
    )
    db.session.add(task)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="create_task",
            detail=f"Created detection task for {file.filename} using model {model_name}",
        )
    )
    db.session.commit()

    app = current_app._get_current_object()
    worker = threading.Thread(
        target=_run_detection_task,
        args=(app, task.id, session["user_id"], session["username"]),
        daemon=True,
    )
    worker.start()

    return jsonify({"ok": True, "message": "Detection task submitted.", "task": serialize_task(task)})


@api_bp.get("/tasks/<int:task_id>")
@login_required
def task_detail(task_id: int):
    task = current_user_filters(DetectionTask.query.filter_by(id=task_id), DetectionTask).first()
    if not task:
        return json_error("未找到检测任务。", 404)
    return jsonify({"ok": True, "task": serialize_task(task)})


@api_bp.get("/records")
@login_required
def records():
    query = current_user_filters(DetectRecord.query.order_by(DetectRecord.detect_time.desc()), DetectRecord)
    items = query.all()
    return jsonify({"ok": True, "items": [serialize_record(item) for item in items]})


@api_bp.get("/records/<int:record_id>")
@login_required
def record_detail(record_id: int):
    record = current_user_filters(DetectRecord.query.filter_by(id=record_id), DetectRecord).first()
    if not record:
        return json_error("未找到检测记录。", 404)

    attack_items = current_user_filters(
        AttackResult.query.filter_by(record_id=record_id).order_by(AttackResult.id.asc()),
        AttackResult,
    ).all()
    return jsonify(
        {
            "ok": True,
            "record": serialize_record(record),
            "attack_results": [serialize_attack_result(item) for item in attack_items],
        }
    )


@api_bp.delete("/records/<int:record_id>")
@admin_required
def delete_record(record_id: int):
    record = DetectRecord.query.get(record_id)
    if not record:
        return json_error("未找到检测记录。", 404)

    AttackResult.query.filter_by(record_id=record.id).delete()
    AlarmLog.query.filter_by(record_id=record.id).delete()
    DetectionTask.query.filter_by(record_id=record.id).update({"record_id": None})
    db.session.delete(record)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="delete_record",
            detail=f"Deleted detect record #{record_id}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.get("/alarms")
@admin_required
def alarms():
    page = max(request.args.get("page", default=1, type=int) or 1, 1)
    page_size = max(request.args.get("page_size", default=20, type=int) or 20, 1)
    page_size = min(page_size, 100)
    status = str(request.args.get("status", "all") or "all").strip()

    query = AlarmLog.query.join(DetectRecord, AlarmLog.record_id == DetectRecord.id).filter(
        DetectRecord.source_file.like("traffic_%")
    )
    if status in {"unprocessed", "processed", "ignored"}:
        query = query.filter(AlarmLog.status == status)

    pagination = query.order_by(AlarmLog.create_time.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return jsonify(
        {
            "ok": True,
            "items": [serialize_alarm(item) for item in pagination.items],
            "pagination": {
                "page": pagination.page,
                "page_size": page_size,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_prev": pagination.has_prev,
                "has_next": pagination.has_next,
                "status": status,
            },
        }
    )


@api_bp.patch("/alarms/<int:alarm_id>")
@admin_required
def update_alarm(alarm_id: int):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip()
    if status not in {"unprocessed", "processed", "ignored"}:
        return json_error("告警状态仅支持 unprocessed、processed 或 ignored。")

    alarm = AlarmLog.query.get(alarm_id)
    if not alarm:
        return json_error("未找到告警记录。", 404)

    alarm.status = status
    db.session.add(
        OperationLog(
            username=session["username"],
            action="update_alarm",
            detail=f"Updated alarm #{alarm.id} to {status}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "alarm": serialize_alarm(alarm)})


@api_bp.get("/models")
@login_required
def models():
    active_model = get_active_model()
    items = ModelInfo.query.order_by(ModelInfo.is_active.desc(), ModelInfo.create_time.desc()).all()
    return jsonify(
        {
            "ok": True,
            "items": [serialize_model(item) for item in items],
            "active_model_id": active_model.id if active_model else None,
        }
    )


@api_bp.get("/traffic-monitor")
@admin_required
def traffic_monitor_status():
    return jsonify({"ok": True, "data": build_traffic_monitor_payload(current_app._get_current_object())})


@api_bp.get("/traffic-monitor/interfaces")
@admin_required
def traffic_monitor_interfaces():
    items = traffic_monitor_service.list_interfaces(current_app._get_current_object())
    return jsonify({"ok": True, "items": items})


@api_bp.patch("/traffic-monitor/config")
@admin_required
def update_traffic_monitor_config():
    payload = request.get_json(silent=True) or {}
    capture_interface = str(payload.get("capture_interface", "")).strip()
    if not capture_interface:
        return json_error("Capture interface is required.")
    app = current_app._get_current_object()
    status = traffic_monitor_service.update_settings(app, capture_interface)
    status["active_model"] = build_traffic_monitor_payload(app)["active_model"]
    return jsonify({"ok": True, "data": status})


@api_bp.post("/traffic-monitor/start")
@admin_required
def start_traffic_monitor():
    app = current_app._get_current_object()
    started = traffic_monitor_service.start(app)
    return jsonify({"ok": True, "started": started, "data": build_traffic_monitor_payload(app)})


@api_bp.post("/traffic-monitor/stop")
@admin_required
def stop_traffic_monitor():
    app = current_app._get_current_object()
    stopped = traffic_monitor_service.stop()
    return jsonify({"ok": True, "stopped": stopped, "data": build_traffic_monitor_payload(app)})


@api_bp.post("/traffic-monitor/test-extract")
@admin_required
def traffic_monitor_test_extract():
    payload = request.get_json(silent=True) or {}
    pcap_name = str(payload.get("pcap_name", "")).strip()
    if not pcap_name:
        return json_error("PCAP file name is required.")

    result = traffic_monitor_service.test_extract(current_app._get_current_object(), pcap_name)
    return jsonify(
        {
            "ok": True,
            "data": build_traffic_monitor_payload(current_app._get_current_object()),
            "result": result,
        }
    )


@api_bp.post("/models")
@admin_required
def create_model():
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    model_name = str(payload.get("model_name", "")).strip()
    model_path = str(payload.get("model_path", "")).strip()
    model_type = str(payload.get("model_type", "PyTorch")).strip() or "PyTorch"
    description = str(payload.get("description", "")).strip()
    dataset_format = str(payload.get("dataset_format", "")).strip()
    try:
        accuracy = float(payload.get("accuracy", 0) or 0)
    except (TypeError, ValueError):
        return json_error("Accuracy must be a valid number.")
    try:
        precision = float(payload.get("precision", 0) or 0)
    except (TypeError, ValueError):
        return json_error("Precision must be a valid number.")
    try:
        recall = float(payload.get("recall", 0) or 0)
    except (TypeError, ValueError):
        return json_error("Recall must be a valid number.")
    try:
        f1_score = float(payload.get("f1_score", 0) or 0)
    except (TypeError, ValueError):
        return json_error("F1-Score must be a valid number.")
    try:
        fpr = float(payload.get("fpr", 0) or 0)
    except (TypeError, ValueError):
        return json_error("FPR must be a valid number.")
    try:
        fnr = float(payload.get("fnr", 0) or 0)
    except (TypeError, ValueError):
        return json_error("FNR must be a valid number.")
    try:
        inference_latency_ms = float(payload.get("inference_latency_ms", 0) or 0)
    except (TypeError, ValueError):
        return json_error("Inference latency must be a valid number.")
    if request.form:
        required_columns_raw = str(payload.get("required_columns", "")).splitlines()
    else:
        required_columns_raw = payload.get("required_columns") or []
    required_columns = [str(item).strip() for item in required_columns_raw if str(item).strip()]
    is_active = bool(payload.get("is_active"))
    upload_file = request.files.get("model_file")

    if upload_file and upload_file.filename:
        suffix = Path(upload_file.filename).suffix.lower()
        if suffix != ".pth":
            return json_error("Only .pth model files are supported.")
        model_dir = Path(current_app.config["MODEL_UPLOAD_FOLDER"])
        model_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{Path(secure_filename(upload_file.filename)).stem}_{threading.get_ident()}{suffix}"
        stored_path = model_dir / stored_name
        upload_file.save(stored_path)
        model_path = str(Path("uploads") / "models" / stored_name)

    if not dataset_format:
        return json_error("Dataset format is required.")
    if not model_name or not model_path:
        return json_error("Model name and model file/path are required.")
    if ModelInfo.query.filter_by(model_path=model_path).first():
        return json_error("A model with the same path already exists.")
    if not Path(resolve_model_path(model_path)).exists():
        return json_error("Model file does not exist in the current workspace.")

    model = ModelInfo(
        model_name=model_name,
        model_path=model_path,
        model_type=model_type,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        fpr=fpr,
        fnr=fnr,
        inference_latency_ms=inference_latency_ms,
        description=description,
        dataset_format=dataset_format,
        required_columns=dump_required_columns(required_columns),
        is_active=False,
    )
    db.session.add(model)
    db.session.flush()
    if is_active or not get_active_model():
        set_active_model(model)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="create_model",
            detail=f"Created model {model_name}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "item": serialize_model(model)})


@api_bp.post("/models/<int:model_id>/activate")
@admin_required
def activate_model(model_id: int):
    model = ModelInfo.query.get(model_id)
    if not model:
        return json_error("Model not found.", 404)
    if not Path(resolve_model_path(model.model_path)).exists():
        return json_error("Model file does not exist in the current workspace.")

    set_active_model(model)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="activate_model",
            detail=f"Activated model {model.model_name}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "item": serialize_model(model)})


@api_bp.delete("/models/<int:model_id>")
@admin_required
def delete_model(model_id: int):
    model = ModelInfo.query.get(model_id)
    if not model:
        return json_error("Model not found.", 404)
    if DetectionTask.query.filter_by(model_id=model_id).first() or DetectRecord.query.filter_by(model_id=model_id).first():
        return json_error("This model already has related tasks or records and cannot be deleted.")

    was_active = model.is_active
    model_name = model.model_name
    db.session.delete(model)
    db.session.flush()
    if was_active:
        replacement = ModelInfo.query.order_by(ModelInfo.create_time.desc()).first()
        if replacement:
            set_active_model(replacement)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="delete_model",
            detail=f"Deleted model {model_name}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.get("/users")
@admin_required
def users():
    items = User.query.order_by(User.create_time.desc()).all()
    return jsonify({"ok": True, "items": [serialize_user(item) for item in items]})


@api_bp.post("/users")
@admin_required
def create_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    role = str(payload.get("role", "user")).strip() or "user"

    if not username or not password:
        return json_error("用户名和密码不能为空。")
    if role not in {"admin", "user"}:
        return json_error("角色仅支持 admin 或 user。")
    if User.query.filter_by(username=username).first():
        return json_error("用户名已存在。")

    user = User(username=username, password=hash_password(password), role=role)
    db.session.add(user)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="create_user",
            detail=f"Created user {username} with role {role}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "user": serialize_user(user)})


@api_bp.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("未找到用户。", 404)

    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", user.username)).strip()
    role = str(payload.get("role", user.role)).strip()
    password = str(payload.get("password", "")).strip()

    if not username:
        return json_error("用户名不能为空。")
    if role not in {"admin", "user"}:
        return json_error("角色仅支持 admin 或 user。")

    existing = User.query.filter(User.username == username, User.id != user_id).first()
    if existing:
        return json_error("用户名已存在。")

    user.username = username
    user.role = role
    if password:
        user.password = hash_password(password)

    if session.get("user_id") == user.id:
        session["username"] = user.username
        session["role"] = user.role

    db.session.add(
        OperationLog(
            username=session["username"],
            action="update_user",
            detail=f"Updated user {user.username} with role {user.role}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "user": serialize_user(user)})


@api_bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("未找到用户。", 404)
    if session.get("user_id") == user.id:
        return json_error("不能删除当前登录账号。")

    if DetectRecord.query.filter_by(user_id=user.id).first():
        return json_error("该用户已有关联检测记录，暂不支持删除。")

    username = user.username
    db.session.delete(user)
    db.session.add(
        OperationLog(
            username=session["username"],
            action="delete_user",
            detail=f"Deleted user {username}",
        )
    )
    db.session.commit()
    return jsonify({"ok": True})
