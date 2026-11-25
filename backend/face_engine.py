import base64
import json
import threading
import urllib.request
import uuid
from datetime import datetime
from urllib.parse import urlparse

import cv2
import numpy as np

try:
    from . import config, db, model_provider
except ImportError:
    import config
    import db
    import model_provider

_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_lock = threading.Lock()


def _recognizer():
    face_module = getattr(cv2, "face", None)
    if face_module is None:
        raise RuntimeError(
            "OpenCV contrib no está instalado. Instala opencv-contrib-python en el backend."
        )
    return face_module.LBPHFaceRecognizer_create()


def _decode_image(data: bytes):
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("El archivo no contiene una imagen válida")
    return image


def _encode_image(image) -> str:
    success, buffer = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88]
    )
    if not success:
        raise RuntimeError("No se pudo codificar la imagen de respuesta")
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return "data:image/jpeg;base64," + encoded


def _find_face(image):
    if _detector.empty():
        raise RuntimeError("No se pudo cargar el detector de rostros de OpenCV")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    equalized = cv2.equalizeHist(gray)
    faces = _detector.detectMultiScale(
        equalized,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(50, 50),
    )
    if len(faces) == 0:
        return None, None, equalized
    x, y, width, height = max(faces, key=lambda item: item[2] * item[3])
    margin_x = int(width * 0.15)
    margin_y = int(height * 0.15)
    image_height, image_width = equalized.shape
    x1 = max(0, int(x) - margin_x)
    y1 = max(0, int(y) - margin_y)
    x2 = min(image_width, int(x + width) + margin_x)
    y2 = min(image_height, int(y + height) + margin_y)
    crop = equalized[y1:y2, x1:x2]
    if crop.size == 0:
        crop = equalized[int(y):int(y + height), int(x):int(x + width)]
    crop = cv2.resize(crop, (200, 200), interpolation=cv2.INTER_AREA)
    crop = cv2.equalizeHist(crop)
    return (int(x), int(y), int(width), int(height)), crop, equalized


def _draw_label(image, box, text) -> None:
    x, y, width, height = box
    cv2.rectangle(image, (x, y), (x + width, y + height), (40, 220, 120), 2)
    cv2.rectangle(image, (x, max(0, y - 30)), (x + width, y), (40, 220, 120), -1)
    cv2.putText(
        image,
        text,
        (x + 6, max(22, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (10, 20, 15),
        2,
        cv2.LINE_AA,
    )


def fetch_camera_image(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("La URL de la cámara debe ser http:// o https://")
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 ProyectoFinal/1.0"}
    )
    with urllib.request.urlopen(
        request, timeout=config.CAMERA_TIMEOUT_SECONDS
    ) as response:
        data = response.read(config.MAX_IMAGE_BYTES + 1)
    if not data:
        raise ValueError("La cámara no devolvió imagen")
    if len(data) > config.MAX_IMAGE_BYTES:
        raise ValueError("La imagen de la cámara es demasiado grande")
    return data


def is_trained() -> bool:
    if config.FACE_MODEL_PROVIDER == "lbph":
        return config.MODEL_PATH.exists() and config.LABELS_PATH.exists()
    return model_provider.is_configured()


def enroll_face(image_bytes: bytes, person_id: int):
    person = db.get_person(person_id)
    if not person:
        raise ValueError("La persona seleccionada no existe")
    image = _decode_image(image_bytes)
    box, crop, _ = _find_face(image)
    if box is None:
        raise ValueError("No se detectó un rostro en la imagen")
    folder = config.FACE_DIR / str(person_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}.jpg"
    if not cv2.imwrite(str(path), crop):
        raise RuntimeError("No se pudo guardar la muestra del rostro")
    sample_id = db.add_face_sample(person_id, str(path))
    return {
        "id": sample_id,
        "person_id": person_id,
        "person_name": person["name"],
        "image_path": str(path),
        "face_box": list(box),
    }


def train():
    if config.FACE_MODEL_PROVIDER != "lbph":
        raise ValueError(
            "El entrenamiento interno solo aplica a LBPH. Con un modelo joblib/keras usa el archivo externo."
        )
    with _lock:
        samples = db.get_face_samples()
        images = []
        labels = []
        label_map = {}
        for sample in samples:
            image = cv2.imread(sample["image_path"], cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            person_id = int(sample["person_id"])
            if person_id not in label_map:
                label_map[person_id] = len(label_map)
            images.append(image)
            labels.append(label_map[person_id])
        if not images:
            raise ValueError("No hay muestras de rostro para entrenar")
        model = _recognizer()
        model.train(images, np.array(labels, dtype=np.int32))
        config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(config.MODEL_PATH))
        payload = {
            "labels": {str(label): person_id for person_id, label in label_map.items()},
            "sample_count": len(images),
            "trained_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        config.LABELS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "sample_count": len(images),
            "person_count": len(label_map),
            "trained_at": payload["trained_at"],
        }


def _load_model():
    if not is_trained():
        return None, None
    payload = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    label_map = {int(key): int(value) for key, value in payload["labels"].items()}
    model = _recognizer()
    model.read(str(config.MODEL_PATH))
    return model, label_map


def recognize(image_bytes: bytes):
    image = _decode_image(image_bytes)
    box, crop, _ = _find_face(image)
    if box is None:
        return {
            "recognized": False,
            "reason": "no_face",
            "message": "No se detectó un rostro en la imagen",
            "annotated_image": _encode_image(image),
        }
    if not is_trained():
        _draw_label(image, box, "Sin entrenar")
        message = (
            "Registra muestras y entrena el modelo antes de reconocer"
            if config.FACE_MODEL_PROVIDER == "lbph"
            else "Configure FACE_MODEL_PATH y FACE_MODEL_LABELS_PATH para el modelo externo"
        )
        return {
            "recognized": False,
            "reason": "not_trained",
            "message": message,
            "annotated_image": _encode_image(image),
        }
    distance = None
    if config.FACE_MODEL_PROVIDER == "lbph":
        model, label_map = _load_model()
        label, distance = model.predict(crop)
        person_id = label_map.get(int(label))
        person = db.get_person(person_id) if person_id else None
        matched = person is not None and float(distance) <= config.FACE_MATCH_THRESHOLD
        confidence = max(0.0, min(100.0, 100.0 - float(distance)))
        distance = round(float(distance), 2)
    else:
        prediction = model_provider.predict(crop)
        person = db.get_person(prediction["person_id"]) if prediction else None
        matched = person is not None
        confidence = prediction["confidence"] if prediction else 0.0
    _draw_label(image, box, person["name"] if matched else "Desconocido")
    return {
        "recognized": matched,
        "reason": "matched" if matched else "unknown_person",
        "message": (
            f"Rostro identificado como {person['name']}"
            if matched
            else "El rostro no coincide con las personas registradas"
        ),
        "person": person if matched else None,
        "confidence": round(confidence, 2) if matched else None,
        "distance": distance,
        "face_box": list(box),
        "annotated_image": _encode_image(image),
    }
