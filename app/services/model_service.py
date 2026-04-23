from __future__ import annotations

import glob
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import numpy as np
import pandas as pd
from flask import current_app
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedShuffleSplit
try:
    from sklearn.preprocessing import StandardScaler
except ImportError:  # pragma: no cover
    StandardScaler = None

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # pragma: no cover
    torch = None
    nn = None
    F = None


SOURCE_IP_CANDIDATES = ["Source IP", "src_ip", "Src IP", "source_ip"]
DEST_IP_CANDIDATES = ["Destination IP", "dst_ip", "Dst IP", "destination_ip"]
DROP_COLUMNS = [
    "Flow ID",
    "Source IP",
    "Source Port",
    "Destination IP",
    "Destination Port",
    "Timestamp",
]
LABEL_DISPLAY_MAP = {
    "BENIGN": "BENIGN",
    "Bot": "Bot",
    "DDoS": "DDoS",
    "DoS GoldenEye": "DoS GoldenEye",
    "DoS Hulk": "DoS Hulk",
    "DoS Slowhttptest": "DoS Slowhttptest",
    "DoS slowloris": "DoS slowloris",
    "FTP-Patator": "FTP-Patator",
    "Heartbleed": "Heartbleed",
    "Infiltration": "Infiltration",
    "PortScan": "PortScan",
    "SSH-Patator": "SSH-Patator",
    "Web Attack \x96 Brute Force": "Web Attack Brute Force",
    "Web Attack \x96 Sql Injection": "Web Attack Sql Injection",
    "Web Attack \x96 XSS": "Web Attack XSS",
    "Web Attack – Brute Force": "Web Attack Brute Force",
    "Web Attack – Sql Injection": "Web Attack Sql Injection",
    "Web Attack – XSS": "Web Attack XSS",
    "Web Attack 每 Brute Force": "Web Attack Brute Force",
    "Web Attack 每 Sql Injection": "Web Attack Sql Injection",
    "Web Attack 每 XSS": "Web Attack XSS",
}
DEFAULT_LABELS = [
    "BENIGN",
    "Bot",
    "DDoS",
    "DoS GoldenEye",
    "DoS Hulk",
    "DoS Slowhttptest",
    "DoS slowloris",
    "FTP-Patator",
    "Heartbleed",
    "Infiltration",
    "PortScan",
    "SSH-Patator",
    "Web Attack \x96 Brute Force",
    "Web Attack \x96 Sql Injection",
    "Web Attack \x96 XSS",
]
BINARY_LABELS = ["BENIGN", "ATTACK"]
TEST_SPLIT_SIZE = 0.1
TEST_SPLIT_SEED = 42


@dataclass
class PredictionRow:
    src_ip: str
    dst_ip: str
    attack_type: str
    confidence: float
    risk_level: str


if nn is not None:
    class Attention(nn.Module):
        def __init__(self, hidden_dim):
            super().__init__()
            self.attention = nn.Linear(hidden_dim, 1, bias=False)

        def forward(self, features):
            attn_scores = self.attention(features)
            attn_weights = F.softmax(attn_scores, dim=1)
            context_vector = torch.sum(attn_weights * features, dim=1)
            return context_vector, attn_weights


    class UniversalIDSModel(nn.Module):
        def __init__(
            self,
            num_features,
            num_classes=15,
            use_cnn=False,
            rnn_type="LSTM",
            bidirectional=False,
            use_attention=False,
        ):
            super().__init__()
            self.use_cnn = use_cnn
            self.rnn_type = rnn_type
            self.use_attention = use_attention

            if self.use_cnn:
                self.cnn = nn.Sequential(
                    nn.Conv1d(1, 64, 3, 1, 1),
                    nn.BatchNorm1d(64),
                    nn.ReLU(),
                    nn.MaxPool1d(2),
                )
                rnn_input_size = 64
                self.cnn_output_len = num_features // 2
            else:
                rnn_input_size = 1

            rnn_hidden_size = 64
            self.num_directions = 2 if bidirectional else 1

            if rnn_type == "LSTM":
                self.rnn = nn.LSTM(
                    rnn_input_size,
                    rnn_hidden_size,
                    2,
                    batch_first=True,
                    bidirectional=bidirectional,
                )
            elif rnn_type == "GRU":
                self.rnn = nn.GRU(
                    rnn_input_size,
                    rnn_hidden_size,
                    2,
                    batch_first=True,
                    bidirectional=bidirectional,
                )
            else:
                self.rnn = None

            if self.use_attention:
                attn_input_dim = rnn_hidden_size * self.num_directions if rnn_type else 64
                self.attention = Attention(attn_input_dim)
                classifier_input_dim = attn_input_dim
            else:
                if rnn_type:
                    classifier_input_dim = rnn_hidden_size * self.num_directions
                else:
                    classifier_input_dim = 64 * self.cnn_output_len

            self.classifier = nn.Sequential(
                nn.Linear(classifier_input_dim, 64),
                nn.Dropout(0.5),
                nn.Linear(64, num_classes),
            )

        def forward(self, x):
            if self.use_cnn:
                x = x.transpose(1, 2)
                x = self.cnn(x)
                x = x.transpose(1, 2)
            if self.rnn_type:
                x, _ = self.rnn(x)
            if self.use_attention:
                x, _ = self.attention(x)
            else:
                if self.rnn_type:
                    x = x[:, -1, :]
                else:
                    x = x.contiguous().view(x.size(0), -1)
            return self.classifier(x)
else:
    Attention = None
    UniversalIDSModel = None


class ModelService:
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.dataset_dir = Path(current_app.config["DATASET_DIR"])
        self.artifact_dir = Path(current_app.config["ARTIFACT_DIR"])
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.preprocess_meta_path = self.artifact_dir / "preprocess_meta.json"
        self.evaluation_cache_path = self.artifact_dir / "evaluation_metrics.json"
        self.device = "cuda" if torch and torch.cuda.is_available() else "cpu"
        self.predict_chunk_size = current_app.config["PREDICT_CHUNK_SIZE"]
        self.inference_batch_size = current_app.config["INFERENCE_BATCH_SIZE"]
        self.label_classes = DEFAULT_LABELS.copy()
        self.model = None
        self.model_signature = {}
        self.feature_columns = []
        self.scaler_mean = []
        self.scaler_scale = []
        self._load_or_build_preprocessor()
        self._load_model()

    def predict_file(self, file_path: str) -> List[PredictionRow]:
        rows = []
        for chunk_rows in self.predict_file_in_chunks(file_path):
            rows.extend(chunk_rows)
        return rows

    def predict_file_in_chunks(self, file_path: str) -> Iterator[List[PredictionRow]]:
        chunk_reader = pd.read_csv(
            file_path,
            low_memory=False,
            encoding="cp1252",
            chunksize=self.predict_chunk_size,
        )
        for raw_df in chunk_reader:
            yield self._predict_chunk(raw_df)

    def evaluate_test_set(self) -> dict:
        cache_signature = self._build_evaluation_signature()
        cached = self._load_cached_evaluation(cache_signature)
        if cached:
            return cached

        dataset_files = sorted(self.dataset_dir.glob("*.csv"))
        if not dataset_files:
            raise FileNotFoundError("未找到可用于评估的测试数据集。")

        label_frames = []
        for file_path in dataset_files:
            labels = pd.read_csv(
                file_path,
                usecols=lambda name: str(name).strip() == "Label",
                low_memory=False,
                encoding="cp1252",
            )
            labels.columns = labels.columns.str.strip()
            label_frames.append(labels["Label"].map(self._normalize_label).rename("Label"))

        all_labels = pd.concat(label_frames, ignore_index=True)
        encoded_labels = all_labels.map(self._encode_true_label)
        valid_mask = encoded_labels.notna()
        if not valid_mask.any():
            raise RuntimeError("测试数据集中没有可用于评估的有效标签。")

        valid_indices = np.flatnonzero(valid_mask.to_numpy())
        valid_targets = encoded_labels[valid_mask].astype(int).to_numpy()

        splitter = StratifiedShuffleSplit(
            n_splits=1,
            test_size=TEST_SPLIT_SIZE,
            random_state=TEST_SPLIT_SEED,
        )
        _, relative_test_indices = next(splitter.split(np.zeros(len(valid_targets)), valid_targets))
        selected_global_indices = set(valid_indices[relative_test_indices].tolist())

        y_true = []
        y_pred = []
        current_index = 0

        for file_path in dataset_files:
            chunk_reader = pd.read_csv(
                file_path,
                low_memory=False,
                encoding="cp1252",
                chunksize=self.predict_chunk_size,
            )
            for raw_df in chunk_reader:
                raw_df.columns = raw_df.columns.str.strip()
                chunk_size = len(raw_df)
                chunk_indices = np.arange(current_index, current_index + chunk_size)
                selected_mask = np.array(
                    [index in selected_global_indices for index in chunk_indices],
                    dtype=bool,
                )
                current_index += chunk_size
                if not selected_mask.any():
                    continue

                selected_df = raw_df.loc[selected_mask].copy()
                normalized_labels = selected_df["Label"].map(self._normalize_label)
                encoded_chunk_labels = normalized_labels.map(self._encode_true_label)
                valid_chunk_mask = encoded_chunk_labels.notna().to_numpy()
                if not valid_chunk_mask.any():
                    continue

                eval_df = selected_df.loc[valid_chunk_mask].copy()
                probabilities = self._predict_probabilities(self._transform_input(eval_df))
                y_true.extend(encoded_chunk_labels.loc[valid_chunk_mask].astype(int).tolist())
                y_pred.extend(np.argmax(probabilities, axis=1).astype(int).tolist())

        if not y_true:
            raise RuntimeError("未能从测试集生成评估样本。")

        labels = list(range(len(self.label_classes)))
        matrix = confusion_matrix(y_true, y_pred, labels=labels)
        result = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
            "f1_score": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
            "test_samples": int(len(y_true)),
            "labels": [self._display_label(label) for label in self.label_classes],
            "confusion_matrix": matrix.astype(int).tolist(),
        }
        self.evaluation_cache_path.write_text(
            json.dumps({"signature": cache_signature, "result": result}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    def _build_evaluation_signature(self) -> dict:
        dataset_files = sorted(self.dataset_dir.glob("*.csv"))
        return {
            "model_path": str(self.model_path.resolve()),
            "model_mtime_ns": self.model_path.stat().st_mtime_ns if self.model_path.exists() else None,
            "model_size": self.model_path.stat().st_size if self.model_path.exists() else None,
            "preprocess_meta_mtime_ns": (
                self.preprocess_meta_path.stat().st_mtime_ns if self.preprocess_meta_path.exists() else None
            ),
            "preprocess_meta_size": (
                self.preprocess_meta_path.stat().st_size if self.preprocess_meta_path.exists() else None
            ),
            "test_split_size": TEST_SPLIT_SIZE,
            "test_split_seed": TEST_SPLIT_SEED,
            "datasets": [
                {
                    "path": str(file_path.resolve()),
                    "mtime_ns": file_path.stat().st_mtime_ns,
                    "size": file_path.stat().st_size,
                }
                for file_path in dataset_files
            ],
        }

    def _load_cached_evaluation(self, expected_signature: dict) -> dict | None:
        if not self.evaluation_cache_path.exists():
            return None
        try:
            cached = json.loads(self.evaluation_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if cached.get("signature") != expected_signature:
            return None
        return cached.get("result")

    def _load_or_build_preprocessor(self):
        if self.preprocess_meta_path.exists():
            meta = json.loads(self.preprocess_meta_path.read_text(encoding="utf-8"))
            self.feature_columns = meta["feature_columns"]
            self.scaler_mean = meta["scaler_mean"]
            self.scaler_scale = meta["scaler_scale"]
            self.label_classes = meta.get("label_classes", DEFAULT_LABELS)
            return

        dataset_files = sorted(glob.glob(str(self.dataset_dir / "*.csv")))
        if not dataset_files:
            raise FileNotFoundError("未找到训练数据集，无法构建预处理器。")

        feature_sum = None
        feature_sq_sum = None
        sample_count = 0
        label_set = set()

        for file in dataset_files:
            df = pd.read_csv(file, low_memory=False, encoding="cp1252")
            df.columns = df.columns.str.strip()
            if "Label" in df.columns:
                label_set.update(str(label).strip() for label in df["Label"].dropna().unique())
            processed = self._prepare_feature_frame(df, fit_mode=True)
            values = processed.to_numpy(dtype=np.float64)
            if feature_sum is None:
                self.feature_columns = processed.columns.tolist()
                feature_sum = np.zeros(values.shape[1], dtype=np.float64)
                feature_sq_sum = np.zeros(values.shape[1], dtype=np.float64)
            feature_sum += values.sum(axis=0)
            feature_sq_sum += np.square(values).sum(axis=0)
            sample_count += values.shape[0]

        mean = feature_sum / sample_count
        variance = np.maximum((feature_sq_sum / sample_count) - np.square(mean), 1e-12)
        scale = np.sqrt(variance)

        self.scaler_mean = mean.tolist()
        self.scaler_scale = scale.tolist()
        self.label_classes = sorted(label_set) if label_set else DEFAULT_LABELS
        self.preprocess_meta_path.write_text(
            json.dumps(
                {
                    "feature_columns": self.feature_columns,
                    "scaler_mean": self.scaler_mean,
                    "scaler_scale": self.scaler_scale,
                    "label_classes": self.label_classes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _prepare_feature_frame(self, df: pd.DataFrame, fit_mode: bool) -> pd.DataFrame:
        df.columns = df.columns.str.strip()
        df = df.replace([np.inf, -np.inf], np.nan)
        if "Label" in df.columns:
            df = df.drop(columns=["Label"])
        df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns], errors="ignore")

        for column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.fillna(df.mean(numeric_only=True))
        df = df.fillna(0)

        if fit_mode:
            return df

        for column in self.feature_columns:
            if column not in df.columns:
                df[column] = 0
        return df[self.feature_columns]

    def _transform_input(self, df: pd.DataFrame):
        processed = self._prepare_feature_frame(df, fit_mode=False)
        scaled = self._scale_features(processed)
        reshaped = np.reshape(
            scaled.astype(np.float32),
            (scaled.shape[0], scaled.shape[1], 1),
        )
        if torch is None:
            raise RuntimeError("当前环境未安装 torch，请先安装 requirements.txt 中的依赖。")
        return torch.tensor(reshaped, dtype=torch.float32).to(self.device)

    def _scale_features(self, processed: pd.DataFrame) -> np.ndarray:
        if StandardScaler is None:
            raise RuntimeError("当前环境未安装 scikit-learn，请先安装 requirements.txt 中的依赖。")
        values = processed.to_numpy(dtype=np.float64)
        mean = np.array(self.scaler_mean, dtype=np.float64)
        scale = np.array(self.scaler_scale, dtype=np.float64)
        safe_scale = np.where(scale == 0, 1.0, scale)
        return (values - mean) / safe_scale

    def _load_model(self):
        if torch is None:
            return
        if not self.feature_columns:
            raise RuntimeError("预处理元数据缺失，无法初始化模型。")
        state_dict = torch.load(self.model_path, map_location=self.device)
        self.model_signature = self._infer_model_signature(state_dict)
        if self.model_signature["num_classes"] == 2:
            self.label_classes = BINARY_LABELS.copy()
        elif len(self.label_classes) < self.model_signature["num_classes"]:
            self.label_classes.extend(
                [f"CLASS_{index}" for index in range(len(self.label_classes), self.model_signature["num_classes"])]
            )
        elif len(self.label_classes) > self.model_signature["num_classes"]:
            self.label_classes = self.label_classes[: self.model_signature["num_classes"]]
        self.model = UniversalIDSModel(
            num_features=len(self.feature_columns),
            num_classes=self.model_signature["num_classes"],
            use_cnn=self.model_signature["use_cnn"],
            rnn_type=self.model_signature["rnn_type"],
            bidirectional=self.model_signature["bidirectional"],
            use_attention=self.model_signature["use_attention"],
        ).to(self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def _infer_model_signature(self, state_dict):
        keys = set(state_dict.keys())
        use_cnn = any(key.startswith("cnn.") for key in keys)
        use_attention = any(key.startswith("attention.") for key in keys)
        has_rnn = any(key.startswith("rnn.") for key in keys)
        if not has_rnn:
            rnn_type = None
        else:
            if any("weight_ih_l0" in key and state_dict[key].shape[0] == 192 for key in keys):
                rnn_type = "GRU"
            else:
                rnn_type = "LSTM"
        bidirectional = any("_reverse" in key for key in keys)

        classifier_weight = state_dict.get("classifier.2.weight")
        if classifier_weight is None:
            raise RuntimeError("未找到 classifier.2.weight，无法推断输出类别数。")
        num_classes = int(classifier_weight.shape[0])

        return {
            "use_cnn": use_cnn,
            "use_attention": use_attention,
            "rnn_type": rnn_type,
            "bidirectional": bidirectional,
            "num_classes": num_classes,
        }

    def _predict_probabilities(self, input_tensor):
        if self.model is None:
            raise RuntimeError("模型尚未加载，请检查 torch 环境和模型文件。")
        batches = []
        with torch.no_grad():
            for start in range(0, input_tensor.shape[0], self.inference_batch_size):
                batch_tensor = input_tensor[start : start + self.inference_batch_size]
                logits = self.model(batch_tensor)
                probs = torch.softmax(logits, dim=1)
                batches.append(probs.detach().cpu().numpy())
        if not batches:
            return np.empty((0, len(self.label_classes)))
        return np.vstack(batches)

    def _display_label(self, label: str) -> str:
        normalized = str(label).strip()
        return LABEL_DISPLAY_MAP.get(normalized, normalized)

    def _normalize_label(self, label: str) -> str:
        normalized = str(label).strip()
        if self.model_signature.get("num_classes") == 2:
            return "BENIGN" if normalized == "BENIGN" else "ATTACK"
        return normalized

    def _encode_true_label(self, label: str):
        normalized = self._normalize_label(label)
        try:
            return self.label_classes.index(normalized)
        except ValueError:
            return None

    def _to_risk_level(self, attack_type: str, confidence: float) -> str:
        if attack_type == "BENIGN":
            return "正常"
        if attack_type in {"Heartbleed", "DDoS", "DoS Hulk", "Infiltration"} or confidence >= 0.9:
            return "高风险"
        if confidence >= 0.75:
            return "中风险"
        return "低风险"

    def _predict_chunk(self, raw_df: pd.DataFrame) -> List[PredictionRow]:
        input_tensor = self._transform_input(raw_df)
        probabilities = self._predict_probabilities(input_tensor)
        pred_indices = np.argmax(probabilities, axis=1)
        confidences = probabilities[np.arange(len(pred_indices)), pred_indices]

        rows = []
        for row_index, (_, row) in enumerate(raw_df.iterrows()):
            attack_label = self._display_label(self.label_classes[int(pred_indices[row_index])])
            confidence = float(confidences[row_index])
            rows.append(
                PredictionRow(
                    src_ip=self._read_ip(row, SOURCE_IP_CANDIDATES),
                    dst_ip=self._read_ip(row, DEST_IP_CANDIDATES),
                    attack_type=attack_label,
                    confidence=confidence,
                    risk_level=self._to_risk_level(attack_label, confidence),
                )
            )
        return rows

    def _read_ip(self, row: pd.Series, candidates: List[str]) -> str:
        for candidate in candidates:
            if candidate in row.index:
                return str(row[candidate])
            stripped_match = [col for col in row.index if str(col).strip() == candidate]
            if stripped_match:
                return str(row[stripped_match[0]])
        return "unknown"
