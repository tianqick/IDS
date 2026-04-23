from __future__ import annotations

import subprocess
import threading
import json
from datetime import datetime
from pathlib import Path

from ..extensions import db
from ..models import OperationLog, User
from .data_service import run_detection
from .model_registry import get_active_model


class TrafficMonitorService:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._app = None
        self._settings = {}
        self._status = {
            "running": False,
            "input_dir": "",
            "archive_dir": "",
            "pcap_dir": "",
            "pcap_archive_dir": "",
            "poll_interval": 0,
            "capture_interface": "",
            "capture_duration": 0,
            "tshark_ready": False,
            "cicflowmeter_ready": False,
            "pipeline_ready": False,
            "available_interfaces": [],
            "last_scan_at": None,
            "last_capture_at": None,
            "last_extract_at": None,
            "last_processed_at": None,
            "last_processed_file": None,
            "last_record_id": None,
            "last_generated_pcap": None,
            "last_generated_csv": None,
            "last_error": None,
            "processed_count": 0,
        }

    def start(self, app):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._app = app
            self._load_settings()
            self._stop_event.clear()
            self._status.update(self._build_status_snapshot(app))
            self._status["running"] = True
            self._status["last_error"] = None
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="traffic-monitor")
            self._thread.start()
            return True

    def stop(self):
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                self._status["running"] = False
                return False
            self._stop_event.set()
            self._status["running"] = False
            return True

    def status(self):
        snapshot = dict(self._status)
        if self._app is not None:
            snapshot.update(self._build_status_snapshot(self._app))
            snapshot["running"] = bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())
        return snapshot

    def list_interfaces(self, app):
        self._app = app
        self._load_settings()
        snapshot = self._build_status_snapshot(app)
        return snapshot.get("available_interfaces", [])

    def update_settings(self, app, capture_interface: str):
        self._app = app
        self._load_settings()
        self._settings["capture_interface"] = str(capture_interface).strip()
        self._save_settings()
        self._status.update(self._build_status_snapshot(app))
        return self.status()

    def _build_status_snapshot(self, app):
        self._load_settings()
        tshark_path = str(app.config.get("TSHARK_PATH", "")).strip()
        extractor_command = str(app.config.get("CICFLOWMETER_COMMAND", "")).strip()
        tshark_ready = bool(tshark_path and Path(tshark_path).exists())
        cic_ready = bool(extractor_command)
        capture_interface = str(self._settings.get("capture_interface") or app.config.get("TRAFFIC_CAPTURE_INTERFACE", "")).strip()
        available_interfaces = self._discover_interfaces(tshark_path) if tshark_ready else []
        pipeline_ready = tshark_ready and cic_ready and bool(capture_interface)
        return {
            "input_dir": app.config["TRAFFIC_FLOW_INPUT_DIR"],
            "archive_dir": app.config["TRAFFIC_FLOW_ARCHIVE_DIR"],
            "pcap_dir": app.config["TRAFFIC_PCAP_DIR"],
            "pcap_archive_dir": app.config["TRAFFIC_PCAP_ARCHIVE_DIR"],
            "poll_interval": app.config["TRAFFIC_MONITOR_INTERVAL"],
            "capture_interface": capture_interface,
            "capture_duration": app.config["TRAFFIC_CAPTURE_DURATION"],
            "tshark_ready": tshark_ready,
            "cicflowmeter_ready": cic_ready,
            "pipeline_ready": pipeline_ready,
            "available_interfaces": available_interfaces,
        }

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception as exc:  # pragma: no cover
                self._status["last_error"] = str(exc)
            self._status["last_scan_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            self._stop_event.wait(self._app.config["TRAFFIC_MONITOR_INTERVAL"])

    def _scan_once(self):
        with self._app.app_context():
            input_dir = Path(self._app.config["TRAFFIC_FLOW_INPUT_DIR"])
            archive_dir = Path(self._app.config["TRAFFIC_FLOW_ARCHIVE_DIR"])
            pcap_dir = Path(self._app.config["TRAFFIC_PCAP_DIR"])
            pcap_archive_dir = Path(self._app.config["TRAFFIC_PCAP_ARCHIVE_DIR"])
            input_dir.mkdir(parents=True, exist_ok=True)
            archive_dir.mkdir(parents=True, exist_ok=True)
            pcap_dir.mkdir(parents=True, exist_ok=True)
            pcap_archive_dir.mkdir(parents=True, exist_ok=True)

            if self.status()["pipeline_ready"]:
                self._capture_and_extract_once(pcap_dir, input_dir, pcap_archive_dir)

            for file_path in sorted(input_dir.glob("*.csv")):
                if self._stop_event.is_set():
                    return
                self._process_file(file_path, archive_dir)

    def _capture_and_extract_once(self, pcap_dir: Path, flow_input_dir: Path, pcap_archive_dir: Path):
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        pcap_path = pcap_dir / f"traffic_{timestamp}.pcapng"
        csv_path = flow_input_dir / f"traffic_{timestamp}.csv"
        self._run_tshark_capture(pcap_path)
        self._status["last_generated_pcap"] = pcap_path.name
        self._status["last_capture_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self._run_cicflowmeter_extract(pcap_path, csv_path)
        self._status["last_generated_csv"] = csv_path.name
        self._status["last_extract_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        archived_pcap = self._unique_destination(pcap_archive_dir, pcap_path.name)
        pcap_path.replace(archived_pcap)

    def _run_tshark_capture(self, pcap_path: Path):
        tshark_path = self._app.config["TSHARK_PATH"]
        interface = str(self._settings.get("capture_interface") or self._app.config["TRAFFIC_CAPTURE_INTERFACE"]).strip()
        duration = self._app.config["TRAFFIC_CAPTURE_DURATION"]
        capture_filter = str(self._app.config.get("TRAFFIC_CAPTURE_FILTER", "")).strip()
        command = [tshark_path, "-i", interface, "-a", f"duration:{duration}", "-w", str(pcap_path)]
        if capture_filter:
            command.extend(["-f", capture_filter])
        self._run_command(command, "tshark capture")

    def _run_cicflowmeter_extract(self, pcap_path: Path, csv_path: Path):
        template = str(self._app.config["CICFLOWMETER_COMMAND"]).strip()
        if not template:
            raise RuntimeError("CICFLOWMETER_COMMAND is not configured.")
        command = template.format(
            pcap=str(pcap_path),
            csv=str(csv_path),
            output_dir=str(csv_path.parent),
            output_name=csv_path.name,
        )
        self._run_command(command, "CICFlowMeter extraction")
        if not csv_path.exists():
            csv_candidates = sorted(csv_path.parent.glob(f"{csv_path.stem}*.csv"))
            if csv_candidates:
                latest = csv_candidates[-1]
                if latest != csv_path:
                    latest.replace(csv_path)
        if not csv_path.exists():
            raise RuntimeError("CICFlowMeter did not produce the expected CSV output.")

    def _run_command(self, command, label: str):
        completed = subprocess.run(
            command,
            shell=isinstance(command, str),
            cwd=self._app.config["UPLOAD_FOLDER"],
            capture_output=True,
            text=False,
            timeout=max(self._app.config["TRAFFIC_CAPTURE_DURATION"] * 2, 30),
        )
        if completed.returncode != 0:
            stderr = self._decode_process_output(completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"{label} failed: {stderr or 'unknown error'}")

    def _process_file(self, file_path: Path, archive_dir: Path):
        active_model = get_active_model()
        system_user = User.query.filter_by(role="admin").order_by(User.id.asc()).first()
        if not system_user:
            raise RuntimeError("No admin user available for traffic monitoring.")

        record = run_detection(
            str(file_path),
            user_id=system_user.id,
            username=system_user.username,
            model_id=active_model.id if active_model else None,
        )

        archive_target = self._unique_destination(archive_dir, file_path.name)
        file_path.replace(archive_target)

        self._status["processed_count"] += 1
        self._status["last_processed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self._status["last_processed_file"] = archive_target.name
        self._status["last_record_id"] = record.id
        self._status["last_error"] = None

        db.session.add(
            OperationLog(
                username=system_user.username,
                action="traffic_monitor_detect",
                detail=f"Processed traffic flow file {archive_target.name}",
            )
        )
        db.session.commit()

    def _unique_destination(self, directory: Path, filename: str) -> Path:
        target = directory / filename
        counter = 1
        while target.exists():
            target = directory / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
            counter += 1
        return target

    def _settings_path(self) -> Path:
        if self._app is None:
            return Path("traffic_monitor_settings.json")
        return Path(self._app.config["ARTIFACT_DIR"]) / "traffic_monitor_settings.json"

    def _load_settings(self):
        path = self._settings_path()
        if not path.exists():
            return
        try:
            self._settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._settings = {}

    def _save_settings(self):
        path = self._settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._settings, ensure_ascii=False, indent=2), encoding="utf-8")

    def _discover_interfaces(self, tshark_path: str):
        if not tshark_path:
            return []
        try:
            completed = subprocess.run(
                [tshark_path, "-D"],
                capture_output=True,
                text=False,
                timeout=15,
            )
        except OSError:
            return []
        if completed.returncode != 0:
            return []
        items = []
        stdout = self._decode_process_output(completed.stdout)
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line or "." not in line:
                continue
            index, description = line.split(".", 1)
            items.append({"id": index.strip(), "label": description.strip()})
        return items

    def _decode_process_output(self, output: bytes | str | None) -> str:
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        for encoding in ("utf-8", "gbk", "cp1252", "latin-1"):
            try:
                return output.decode(encoding)
            except UnicodeDecodeError:
                continue
        return output.decode("utf-8", errors="replace")


traffic_monitor_service = TrafficMonitorService()
