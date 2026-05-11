from __future__ import annotations

import csv
import subprocess
import threading
import json
import tempfile
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import OperationLog, User
from .data_service import run_detection
from .model_registry import get_active_model

PYTHON_CICFLOWMETER_FIELD_MAP = {
    "src_ip": "Source IP",
    "dst_ip": "Destination IP",
    "src_port": "Source Port",
    "dst_port": "Destination Port",
    "protocol": "Protocol",
    "timestamp": "Timestamp",
    "flow_duration": "Flow Duration",
    "flow_byts_s": "Flow Bytes/s",
    "flow_pkts_s": "Flow Packets/s",
    "fwd_pkts_s": "Fwd Packets/s",
    "bwd_pkts_s": "Bwd Packets/s",
    "tot_fwd_pkts": "Total Fwd Packets",
    "tot_bwd_pkts": "Total Backward Packets",
    "totlen_fwd_pkts": "Total Length of Fwd Packets",
    "totlen_bwd_pkts": "Total Length of Bwd Packets",
    "fwd_pkt_len_max": "Fwd Packet Length Max",
    "fwd_pkt_len_min": "Fwd Packet Length Min",
    "fwd_pkt_len_mean": "Fwd Packet Length Mean",
    "fwd_pkt_len_std": "Fwd Packet Length Std",
    "bwd_pkt_len_max": "Bwd Packet Length Max",
    "bwd_pkt_len_min": "Bwd Packet Length Min",
    "bwd_pkt_len_mean": "Bwd Packet Length Mean",
    "bwd_pkt_len_std": "Bwd Packet Length Std",
    "pkt_len_max": "Max Packet Length",
    "pkt_len_min": "Min Packet Length",
    "pkt_len_mean": "Packet Length Mean",
    "pkt_len_std": "Packet Length Std",
    "pkt_len_var": "Packet Length Variance",
    "fwd_header_len": "Fwd Header Length",
    "bwd_header_len": "Bwd Header Length",
    "fwd_seg_size_min": "min_seg_size_forward",
    "fwd_act_data_pkts": "act_data_pkt_fwd",
    "flow_iat_mean": "Flow IAT Mean",
    "flow_iat_max": "Flow IAT Max",
    "flow_iat_min": "Flow IAT Min",
    "flow_iat_std": "Flow IAT Std",
    "fwd_iat_tot": "Fwd IAT Total",
    "fwd_iat_max": "Fwd IAT Max",
    "fwd_iat_min": "Fwd IAT Min",
    "fwd_iat_mean": "Fwd IAT Mean",
    "fwd_iat_std": "Fwd IAT Std",
    "bwd_iat_tot": "Bwd IAT Total",
    "bwd_iat_max": "Bwd IAT Max",
    "bwd_iat_min": "Bwd IAT Min",
    "bwd_iat_mean": "Bwd IAT Mean",
    "bwd_iat_std": "Bwd IAT Std",
    "fwd_psh_flags": "Fwd PSH Flags",
    "bwd_psh_flags": "Bwd PSH Flags",
    "fwd_urg_flags": "Fwd URG Flags",
    "bwd_urg_flags": "Bwd URG Flags",
    "fin_flag_cnt": "FIN Flag Count",
    "syn_flag_cnt": "SYN Flag Count",
    "rst_flag_cnt": "RST Flag Count",
    "psh_flag_cnt": "PSH Flag Count",
    "ack_flag_cnt": "ACK Flag Count",
    "urg_flag_cnt": "URG Flag Count",
    "ece_flag_cnt": "ECE Flag Count",
    "down_up_ratio": "Down/Up Ratio",
    "pkt_size_avg": "Average Packet Size",
    "init_fwd_win_byts": "Init_Win_bytes_forward",
    "init_bwd_win_byts": "Init_Win_bytes_backward",
    "active_max": "Active Max",
    "active_min": "Active Min",
    "active_mean": "Active Mean",
    "active_std": "Active Std",
    "idle_max": "Idle Max",
    "idle_min": "Idle Min",
    "idle_mean": "Idle Mean",
    "idle_std": "Idle Std",
    "fwd_byts_b_avg": "Fwd Avg Bytes/Bulk",
    "fwd_pkts_b_avg": "Fwd Avg Packets/Bulk",
    "bwd_byts_b_avg": "Bwd Avg Bytes/Bulk",
    "bwd_pkts_b_avg": "Bwd Avg Packets/Bulk",
    "fwd_blk_rate_avg": "Fwd Avg Bulk Rate",
    "bwd_blk_rate_avg": "Bwd Avg Bulk Rate",
    "fwd_seg_size_avg": "Avg Fwd Segment Size",
    "bwd_seg_size_avg": "Avg Bwd Segment Size",
    "cwr_flag_count": "CWE Flag Count",
    "subflow_fwd_pkts": "Subflow Fwd Packets",
    "subflow_bwd_pkts": "Subflow Bwd Packets",
    "subflow_fwd_byts": "Subflow Fwd Bytes",
    "subflow_bwd_byts": "Subflow Bwd Bytes",
}


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
            "scapy_ready": False,
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
            "last_capture_status": "idle",
            "last_extract_status": "idle",
            "last_capture_error": None,
            "last_extract_error": None,
            "last_extract_output": None,
            "last_test_result": None,
            "extractor_backend": "python-cicflowmeter",
            "last_error": None,
            "processed_count": 0,
            "empty_feature_count": 0,
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

    def status(self, app=None):
        if app is not None:
            self._app = app
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
        scapy_ready = self._scapy_available()
        cic_ready = self._python_cicflowmeter_available()
        capture_interface = str(self._settings.get("capture_interface") or app.config.get("TRAFFIC_CAPTURE_INTERFACE", "")).strip()
        available_interfaces = self._discover_interfaces() if scapy_ready else []
        resolved_interface = self._resolve_capture_interface(capture_interface, available_interfaces)
        pipeline_ready = scapy_ready and cic_ready and bool(resolved_interface)
        return {
            "input_dir": app.config["TRAFFIC_FLOW_INPUT_DIR"],
            "archive_dir": app.config["TRAFFIC_FLOW_ARCHIVE_DIR"],
            "pcap_dir": app.config["TRAFFIC_PCAP_DIR"],
            "pcap_archive_dir": app.config["TRAFFIC_PCAP_ARCHIVE_DIR"],
            "poll_interval": app.config["TRAFFIC_MONITOR_INTERVAL"],
            "capture_interface": capture_interface,
            "capture_duration": app.config["TRAFFIC_CAPTURE_DURATION"],
            "scapy_ready": scapy_ready,
            "tshark_ready": scapy_ready,
            "cicflowmeter_ready": cic_ready,
            "pipeline_ready": pipeline_ready,
            "available_interfaces": available_interfaces,
            "extractor_backend": "python-cicflowmeter",
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
        pcap_path = pcap_dir / f"traffic_{timestamp}.pcap"
        csv_path = flow_input_dir / f"traffic_{timestamp}.csv"
        self._status["last_capture_status"] = "running"
        self._status["last_capture_error"] = None
        self._status["last_extract_status"] = "idle"
        self._status["last_extract_error"] = None
        self._status["last_extract_output"] = None
        try:
            self._run_scapy_capture(pcap_path)
        except Exception as exc:
            self._status["last_capture_status"] = "failed"
            self._status["last_capture_error"] = str(exc)
            self._status["last_error"] = str(exc)
            raise
        self._status["last_capture_status"] = "success"
        self._status["last_generated_pcap"] = pcap_path.name
        self._status["last_capture_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        self._status["last_extract_status"] = "running"
        try:
            extract_result = self._run_cicflowmeter_extract(pcap_path, csv_path)
        except Exception as exc:
            self._status["last_extract_status"] = "failed"
            self._status["last_extract_error"] = str(exc)
            self._status["last_error"] = str(exc)
            raise
        self._status["last_extract_status"] = "success"
        self._status["last_generated_csv"] = csv_path.name
        self._status["last_extract_output"] = extract_result.get("summary")
        self._status["last_extract_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        archived_pcap = self._unique_destination(pcap_archive_dir, pcap_path.name)
        pcap_path.replace(archived_pcap)

    def _run_scapy_capture(self, pcap_path: Path):
        sniff, wrpcap, _ = self._require_scapy()
        configured_interface = str(
            self._settings.get("capture_interface") or self._app.config["TRAFFIC_CAPTURE_INTERFACE"]
        ).strip()
        interface = self._resolve_capture_interface(configured_interface)
        if not interface:
            raise RuntimeError("Traffic capture interface is not configured or could not be resolved.")
        duration = self._app.config["TRAFFIC_CAPTURE_DURATION"]
        capture_filter = str(self._app.config.get("TRAFFIC_CAPTURE_FILTER", "")).strip()
        sniff_kwargs = {
            "iface": interface,
            "timeout": duration,
            "store": True,
        }
        if capture_filter:
            sniff_kwargs["filter"] = capture_filter
        packets = sniff(**sniff_kwargs)
        wrpcap(str(pcap_path), packets)

    def _run_cicflowmeter_extract(self, pcap_path: Path, csv_path: Path):
        if not self._python_cicflowmeter_available():
            raise RuntimeError("Python cicflowmeter is not available in the current environment.")
        app = self._app or current_app._get_current_object()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        workspace_dir = Path(app.config["UPLOAD_FOLDER"]).resolve().parent
        with tempfile.NamedTemporaryFile(
            prefix=f"{csv_path.stem}_raw_",
            suffix=".csv",
            dir=workspace_dir,
            delete=False,
        ) as raw_temp:
            raw_csv_path = Path(raw_temp.name)
        with tempfile.NamedTemporaryFile(
            prefix=f"{csv_path.stem}_normalized_",
            suffix=".csv",
            dir=workspace_dir,
            delete=False,
        ) as normalized_temp:
            normalized_csv_path = Path(normalized_temp.name)

        if raw_csv_path.exists():
            raw_csv_path.unlink()
        if normalized_csv_path.exists():
            normalized_csv_path.unlink()

        self._run_python_cicflowmeter_extract(pcap_path, raw_csv_path)
        self._normalize_python_cicflowmeter_csv(raw_csv_path, normalized_csv_path)
        normalized_csv_path.replace(csv_path)
        if raw_csv_path.exists():
            raw_csv_path.unlink()
        if not csv_path.exists():
            raise RuntimeError("CICFlowMeter did not produce the expected CSV output.")
        return {
            "command": "python-cicflowmeter-flow-session",
            "output": f"Extracted {pcap_path.name} with python cicflowmeter",
            "summary": f"Python cicflowmeter extracted and normalized {csv_path.name}",
            "csv_path": str(csv_path),
            "has_data_rows": self._csv_has_data_rows(csv_path),
        }

    def _csv_has_data_rows(self, csv_path: Path) -> bool:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            next(reader, None)
            return any(any(str(cell).strip() for cell in row) for row in reader)

    def _build_cicflowmeter_command(self, pcap_path: Path, csv_path: Path):
        jar_path = str(self._app.config.get("CICFLOWMETER_JAR_PATH", "")).strip()
        library_path = str(self._app.config.get("JNETPCAP_LIBRARY_PATH", "")).strip()
        if jar_path and library_path:
            return [
                "java",
                f"-Djava.library.path={library_path}",
                "-cp",
                jar_path,
                "cic.cs.unb.ca.ifm.Cmd",
                str(pcap_path),
                str(csv_path.parent),
            ]

        template = str(self._app.config.get("CICFLOWMETER_COMMAND", "")).strip()
        if not template:
            return None
        return template.format(
            pcap=str(pcap_path),
            csv=str(csv_path),
            output_dir=str(csv_path.parent),
            output_name=csv_path.name,
        )

    def _run_command(self, command, label: str):
        project_root = str(Path(self._app.config["UPLOAD_FOLDER"]).resolve().parent)
        try:
            completed = subprocess.run(
                command,
                shell=isinstance(command, str),
                cwd=project_root,
                capture_output=True,
                text=False,
                timeout=max(self._app.config["TRAFFIC_CAPTURE_DURATION"] * 4, 180),
            )
        except subprocess.TimeoutExpired as exc:
            output = self._decode_process_output((exc.stderr or b"") + (exc.stdout or b"")).strip()
            raise RuntimeError(f"{label} timed out: {output or 'process did not finish in time'}") from exc
        if completed.returncode != 0:
            stderr = self._decode_process_output(completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"{label} failed: {stderr or 'unknown error'}")
        combined_output = self._decode_process_output((completed.stdout or b"") + (completed.stderr or b"")).strip()
        return {
            "command": command if isinstance(command, str) else " ".join(str(item) for item in command),
            "output": combined_output,
        }

    def test_extract(self, app, pcap_name: str):
        self._app = app
        pcap_path = self._resolve_test_pcap_path(pcap_name)
        output_dir = Path(app.config["UPLOAD_FOLDER"]).resolve().parent
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"{pcap_path.stem}.csv"
        if csv_path.exists():
            csv_path.unlink()
        before_files = {item.name for item in output_dir.glob("*.csv")}
        started_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        try:
            extract_result = self._run_cicflowmeter_extract(pcap_path, csv_path)
            after_files = sorted(item.name for item in output_dir.glob("*.csv") if item.name not in before_files)
            result = {
                "ok": True,
                "pcap_path": str(pcap_path),
                "pcap_size": pcap_path.stat().st_size,
                "csv_path": extract_result["csv_path"],
                "has_data_rows": extract_result["has_data_rows"],
                "generated_files": after_files,
                "command": extract_result["command"],
                "output_summary": extract_result["summary"],
                "output": extract_result["output"],
                "started_at": started_at,
                "finished_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as exc:
            result = {
                "ok": False,
                "pcap_path": str(pcap_path),
                "pcap_size": pcap_path.stat().st_size if pcap_path.exists() else 0,
                "csv_path": str(csv_path),
                "has_data_rows": False,
                "generated_files": sorted(item.name for item in output_dir.glob("*.csv") if item.name not in before_files),
                "command": "python-cicflowmeter-flow-session",
                "output_summary": str(exc),
                "output": "",
                "started_at": started_at,
                "finished_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        self._status["last_test_result"] = result
        return result

    def _process_file(self, file_path: Path, archive_dir: Path):
        if not self._csv_has_data_rows(file_path):
            archive_target = self._unique_destination(archive_dir, file_path.name)
            file_path.replace(archive_target)
            self._status["empty_feature_count"] += 1
            self._status["last_processed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            self._status["last_processed_file"] = archive_target.name
            self._status["last_error"] = None
            return

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

    def _discover_interfaces(self):
        try:
            _, _, conf = self._require_scapy()
        except RuntimeError:
            return []

        items = []
        seen = set()
        for index, iface in enumerate(conf.ifaces.values(), start=1):
            name = str(getattr(iface, "name", "") or getattr(iface, "network_name", "") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            description = str(
                getattr(iface, "description", "")
                or getattr(iface, "network_name", "")
                or getattr(iface, "friendly_name", "")
                or name
            ).strip()
            items.append({"id": str(index), "name": name, "label": description})
        return items

    def _resolve_capture_interface(self, capture_interface: str, available_interfaces=None) -> str:
        raw_value = str(capture_interface or "").strip()
        if not raw_value:
            return ""
        items = available_interfaces if available_interfaces is not None else self._discover_interfaces()
        for item in items:
            if raw_value in {str(item.get("id", "")).strip(), str(item.get("name", "")).strip()}:
                return str(item.get("name", "")).strip()
        return raw_value

    def _scapy_available(self) -> bool:
        try:
            self._require_scapy()
            return True
        except RuntimeError:
            return False

    def _require_scapy(self):
        try:
            from scapy.all import conf, sniff, wrpcap
        except ImportError as exc:
            raise RuntimeError("Scapy is not installed. Please install it with pip install scapy.") from exc
        return sniff, wrpcap, conf

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

    def _summarize_process_output(self, output: str) -> str:
        lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
        if not lines:
            return ""
        return " | ".join(lines[-3:])

    def _resolve_test_pcap_path(self, pcap_name: str) -> Path:
        raw_value = str(pcap_name or "").strip()
        if not raw_value:
            raise RuntimeError("PCAP file name is required.")

        candidates = []
        if self._app is not None:
            candidates.extend(
                [
                    Path(self._app.config["TRAFFIC_PCAP_DIR"]),
                    Path(self._app.config["TRAFFIC_PCAP_ARCHIVE_DIR"]),
                ]
            )

        requested = Path(raw_value)
        if requested.is_absolute():
            path = requested.resolve()
            if path.exists():
                return path

        for base_dir in candidates:
            path = (base_dir / requested.name).resolve()
            if path.exists():
                return path

        raise RuntimeError(f"PCAP file not found: {raw_value}")

    def _python_cicflowmeter_available(self) -> bool:
        try:
            from cicflowmeter.flow_session import FlowSession  # noqa: F401
            from scapy.utils import PcapReader  # noqa: F401
            return True
        except ImportError:
            return False

    def _run_python_cicflowmeter_extract(self, pcap_path: Path, raw_csv_path: Path) -> None:
        from cicflowmeter.flow_session import FlowSession
        from scapy.utils import PcapReader

        session = FlowSession(output_mode="csv", output=str(raw_csv_path), fields=None, verbose=False)
        packet_count = 0
        with PcapReader(str(pcap_path)) as reader:
            for pkt in reader:
                session.process(pkt)
                packet_count += 1
        session.flush_flows()
        if packet_count == 0:
            raise RuntimeError("Python cicflowmeter did not read any packets from the PCAP.")
        if not raw_csv_path.exists():
            raise RuntimeError("Python cicflowmeter did not create the raw CSV output.")

    def _normalize_python_cicflowmeter_csv(self, raw_csv_path: Path, csv_path: Path) -> None:
        with raw_csv_path.open("r", encoding="utf-8", newline="") as source_file:
            rows = [row for row in csv.DictReader(source_file) if any(str(value).strip() for value in row.values())]

        normalized_columns = self._normalized_cicflowmeter_columns()
        with csv_path.open("w", encoding="utf-8-sig", newline="") as target_file:
            writer = csv.DictWriter(target_file, fieldnames=normalized_columns)
            writer.writeheader()
            for index, row in enumerate(rows, start=1):
                normalized = {column: 0 for column in normalized_columns}
                for source_name, target_name in PYTHON_CICFLOWMETER_FIELD_MAP.items():
                    normalized[target_name] = row.get(source_name, "")
                normalized["Flow ID"] = (
                    f"{row.get('src_ip', '')}-{row.get('src_port', '')}-"
                    f"{row.get('dst_ip', '')}-{row.get('dst_port', '')}-{index}"
                )
                normalized["Fwd Header Length.1"] = normalized["Fwd Header Length"]
                writer.writerow(normalized)

    def _normalized_cicflowmeter_columns(self) -> list[str]:
        return [
            "Flow ID",
            "Source IP",
            "Source Port",
            "Destination IP",
            "Destination Port",
            "Protocol",
            "Timestamp",
            "Flow Duration",
            "Total Fwd Packets",
            "Total Backward Packets",
            "Total Length of Fwd Packets",
            "Total Length of Bwd Packets",
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
            "Min Packet Length",
            "Max Packet Length",
            "Packet Length Mean",
            "Packet Length Std",
            "Packet Length Variance",
            "FIN Flag Count",
            "SYN Flag Count",
            "RST Flag Count",
            "PSH Flag Count",
            "ACK Flag Count",
            "URG Flag Count",
            "CWE Flag Count",
            "ECE Flag Count",
            "Down/Up Ratio",
            "Average Packet Size",
            "Avg Fwd Segment Size",
            "Avg Bwd Segment Size",
            "Fwd Header Length.1",
            "Fwd Avg Bytes/Bulk",
            "Fwd Avg Packets/Bulk",
            "Fwd Avg Bulk Rate",
            "Bwd Avg Bytes/Bulk",
            "Bwd Avg Packets/Bulk",
            "Bwd Avg Bulk Rate",
            "Subflow Fwd Packets",
            "Subflow Fwd Bytes",
            "Subflow Bwd Packets",
            "Subflow Bwd Bytes",
            "Init_Win_bytes_forward",
            "Init_Win_bytes_backward",
            "act_data_pkt_fwd",
            "min_seg_size_forward",
            "Active Mean",
            "Active Std",
            "Active Max",
            "Active Min",
            "Idle Mean",
            "Idle Std",
            "Idle Max",
            "Idle Min",
        ]


traffic_monitor_service = TrafficMonitorService()
