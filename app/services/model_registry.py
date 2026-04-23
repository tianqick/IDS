from __future__ import annotations

import json
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import ModelInfo


def parse_required_columns(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in str(raw_value).replace("\r", "").split("\n")]
    if isinstance(parsed, str):
        parsed = [parsed]
    return [str(item).strip() for item in parsed if str(item).strip()]


def dump_required_columns(columns: list[str]) -> str:
    return json.dumps(columns, ensure_ascii=False)


def resolve_model_path(model_path: str) -> str:
    candidate = Path(model_path)
    if candidate.is_absolute():
        return str(candidate)
    base_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve().parent
    return str((base_dir / candidate).resolve())


def get_active_model() -> ModelInfo | None:
    return ModelInfo.query.filter_by(is_active=True).order_by(ModelInfo.id.desc()).first()


def get_model_for_detection(model_id: int | None) -> tuple[int | None, str, str, str]:
    model = None
    if model_id:
        model = ModelInfo.query.get(model_id)
    if model is None:
        model = get_active_model()

    if model is not None:
        return model.id, model.model_name, model.model_path, resolve_model_path(model.model_path)

    fallback_path = current_app.config["MODEL_PATH"]
    fallback_name = Path(fallback_path).stem
    return None, fallback_name, fallback_path, resolve_model_path(fallback_path)


def set_active_model(model: ModelInfo) -> None:
    ModelInfo.query.filter(ModelInfo.id != model.id, ModelInfo.is_active.is_(True)).update({"is_active": False})
    model.is_active = True
    db.session.add(model)
