import base64
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from . import config, db, face_engine, focus
except ImportError:
    import config
    import db
    import face_engine
    import focus


class RecognizePayload(BaseModel):
    image_base64: str | None = None


class OwnerPayload(BaseModel):
    owner_id: int


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Reconocimiento de dueños de vehículos", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _decode_base64(value: str) -> bytes:
    if value.startswith("data:"):
        value = value.split(",", 1)[-1]
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 de imagen inválido")


def _camera_bytes():
    if not config.CAMERA_URL:
        raise HTTPException(
            status_code=400,
            detail="Cámara no configurada. Defina IPWEBCAM_URL en el backend.",
        )
    try:
        return face_engine.fetch_camera_image(config.CAMERA_URL)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="No se pudo capturar de la cámara configurada.",
        )


def _source_bytes(file: UploadFile | None, image_base64: str | None):
    if file is not None:
        return file.file.read()
    if image_base64:
        return _decode_base64(image_base64)
    return _camera_bytes()


def _recognize_bytes(image_bytes: bytes):
    try:
        result = face_engine.recognize(image_bytes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    result["focus"] = (
        focus.activate_for(result["person"]["id"])
        if result["recognized"]
        else focus.turn_off_all()
    )
    return result


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model_trained": face_engine.is_trained(),
        "model_provider": config.FACE_MODEL_PROVIDER,
        "camera_configured": bool(config.CAMERA_URL),
    }


@app.get("/api/people")
def people():
    return db.get_people()


@app.get("/api/vehicles")
def vehicles():
    return db.get_vehicles()


@app.put("/api/vehicles/{vehicle_id}/owner")
def change_owner(vehicle_id: int, payload: OwnerPayload):
    try:
        vehicle = db.set_vehicle_owner(vehicle_id, payload.owner_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    focus.turn_off_all()
    return {"message": "Dueño actualizado", "vehicle": vehicle}


@app.get("/api/focus")
def focus_state():
    return focus.get_state()


@app.post("/api/focus/off")
def focus_off():
    return focus.turn_off_all()


@app.get("/api/camera/status")
def camera_status():
    return {"configured": bool(config.CAMERA_URL)}


@app.get("/api/camera/snapshot")
def camera_snapshot():
    return Response(content=_camera_bytes(), media_type="image/jpeg")


@app.post("/api/recognize")
async def recognize_upload(file: UploadFile | None = File(None)):
    return _recognize_bytes(_source_bytes(file, None))


@app.post("/api/recognize/json")
def recognize_json(payload: RecognizePayload):
    return _recognize_bytes(_source_bytes(None, payload.image_base64))


@app.get("/api/faces/status")
def face_status():
    status = db.get_face_status()
    return {
        "trained": face_engine.is_trained(),
        "provider": config.FACE_MODEL_PROVIDER,
        "people": status,
        "total_samples": sum(item["sample_count"] for item in status),
    }


@app.post("/api/faces/enroll")
async def enroll(
    person_id: int = Form(...),
    file: UploadFile | None = File(None),
):
    image_bytes = _source_bytes(file, None)
    try:
        sample = face_engine.enroll_face(image_bytes, person_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"message": "Muestra registrada", "sample": sample}


@app.post("/api/faces/train")
def train():
    try:
        return face_engine.train()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "frontend" / "dist"

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

if (DIST_DIR / "index.html").exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        return FileResponse(DIST_DIR / "index.html")
