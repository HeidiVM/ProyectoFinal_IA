import json
from pathlib import Path

import cv2
import numpy as np

try:
    from . import config, db
except ImportError:
    import config
    import db

_cache = {}


def is_configured() -> bool:
    provider = config.FACE_MODEL_PROVIDER
    return (
        provider in {"joblib", "keras"}
        and bool(config.FACE_MODEL_PATH)
        and config.FACE_MODEL_PATH.exists()
        and bool(config.FACE_MODEL_LABELS_PATH)
        and config.FACE_MODEL_LABELS_PATH.exists()
    )


def threshold_percent() -> float:
    value = config.FACE_MODEL_THRESHOLD
    return value * 100 if value <= 1 else value


def _read_labels():
    payload = json.loads(config.FACE_MODEL_LABELS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        raw = {index: value for index, value in enumerate(payload)}
    elif isinstance(payload, dict):
        raw = payload.get("labels", payload.get("id_to_name", payload))
    else:
        raw = {}
    labels = {}
    for key, value in raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        labels[index] = value
    return labels


def _load_model():
    provider = config.FACE_MODEL_PROVIDER
    if provider in _cache:
        return _cache[provider]
    if provider == "joblib":
        try:
            import joblib
        except ImportError:
            raise ValueError("Instala joblib en el backend para usar FACE_MODEL_PROVIDER=joblib")
        model = joblib.load(str(config.FACE_MODEL_PATH))
    elif provider == "keras":
        try:
            from tensorflow import keras
        except ImportError:
            raise ValueError("Instala tensorflow en el backend para usar FACE_MODEL_PROVIDER=keras")
        model = keras.models.load_model(str(config.FACE_MODEL_PATH))
    else:
        raise ValueError(f"Proveedor de modelo no soportado: {provider}")
    _cache[provider] = model
    return model


def _predict_joblib(model, crop):
    array = np.asarray(crop, dtype=np.float32)
    candidates = [
        array.reshape(1, -1),
        array[None, ...],
        array[None, ..., None],
    ]
    last_error = None
    for candidate in candidates:
        for method_name in ("predict_proba", "predict"):
            method = getattr(model, method_name, None)
            if method is None:
                continue
            try:
                return method(candidate)
            except Exception as error:
                last_error = error
    raise ValueError(f"La entrada del modelo joblib no es compatible: {last_error}")


def _keras_input(model, crop):
    shape = getattr(model, "input_shape", None)
    if isinstance(shape, list):
        shape = shape[0] if shape else None
    height, width = config.FACE_MODEL_INPUT_SIZE
    channels = 3
    if shape and len(shape) == 4:
        if shape[1] and shape[2]:
            height, width = int(shape[1]), int(shape[2])
        if shape[3]:
            channels = int(shape[3])
    resized = cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA)
    if channels == 1:
        array = resized[None, ..., None]
    else:
        array = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)[None, ...]
    return np.asarray(array, dtype=np.float32) / 255.0


def _predict_keras(model, crop):
    return model.predict(_keras_input(model, crop), verbose=0)


def _to_probabilities(raw, label_count):
    if isinstance(raw, str):
        return raw, 100.0
    array = np.asarray(raw)
    if array.ndim == 0:
        value = array.item()
        if isinstance(value, str):
            return value, 100.0
        number = float(value)
        if number.is_integer() and 0 <= number < label_count:
            return int(number), 100.0
        return number, 100.0
    if array.ndim > 1:
        array = array[0]
    if array.dtype.kind in {"U", "S", "O"}:
        value = array.item() if array.size == 1 else array.tolist()
        return str(value), 100.0
    values = array.astype(float)
    if values.size == 1:
        number = float(values.item())
        if number.is_integer() and 0 <= number < label_count:
            return int(number), 100.0
        return number, 100.0
    total = float(values.sum())
    confidence = 100.0
    if 0 < total and abs(total - 1.0) < 0.25:
        confidence = float(values.max()) * 100.0
    return int(values.argmax()), confidence


def _person_from_label(value, labels):
    if isinstance(value, (int, np.integer)):
        target = labels.get(int(value), int(value))
    elif isinstance(value, (float, np.floating)) and float(value).is_integer():
        target = labels.get(int(value), int(value))
    else:
        target = value
    if isinstance(target, dict):
        target = target.get("name") or target.get("person_name") or target.get("id")
    if isinstance(target, (int, np.integer)):
        return db.get_person(int(target))
    if isinstance(target, str):
        if target.isdigit():
            person = db.get_person(int(target))
            if person:
                return person
        wanted = target.strip().lower()
        for person in db.get_people():
            if person["name"].strip().lower() == wanted:
                return person
    return None


def predict(crop):
    if not is_configured():
        return None
    labels = _read_labels()
    if not labels:
        raise ValueError("El archivo de etiquetas del modelo externo está vacío")
    model = _load_model()
    if config.FACE_MODEL_PROVIDER == "joblib":
        raw = _predict_joblib(model, crop)
    else:
        raw = _predict_keras(model, crop)
    value, confidence = _to_probabilities(raw, len(labels))
    person = _person_from_label(value, labels)
    if not person or confidence < threshold_percent():
        return None
    return {
        "person_id": person["id"],
        "person_name": person["name"],
        "confidence": round(float(confidence), 2),
    }
