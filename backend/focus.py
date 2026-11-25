import json
import urllib.request

try:
    from . import config, db
except ImportError:
    import config
    import db


def _send_webhook(payload: dict):
    if not config.FOCUS_WEBHOOK_URL:
        return None
    request = urllib.request.Request(
        config.FOCUS_WEBHOOK_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.status


def _send_serial(vehicle, owner_name: str, action: str):
    if not config.FOCUS_SERIAL_PORT:
        return None
    try:
        import serial
    except ImportError:
        return "pyserial no está instalado"
    template = (
        config.FOCUS_SERIAL_TEMPLATE
        if action == "on"
        else "OFF {plate} {owner}\n"
    )
    message = template.format(
        plate=vehicle["plate"] if vehicle else "",
        owner=owner_name,
        person_id=vehicle["owner_id"] if vehicle else "",
        vehicle_id=vehicle["id"] if vehicle else "",
    )
    with serial.Serial(
        config.FOCUS_SERIAL_PORT, config.FOCUS_SERIAL_BAUDRATE, timeout=1
    ) as port:
        port.write(message.encode("utf-8"))
    return message.strip()


def _deliver(vehicle, owner_name: str, action: str):
    payload = {
        "type": "focus",
        "action": action,
        "vehicle_id": vehicle["id"] if vehicle else None,
        "plate": vehicle["plate"] if vehicle else None,
        "owner": owner_name,
    }
    result = {
        "webhook_status": None,
        "serial_message": None,
        "error": None,
    }
    try:
        result["webhook_status"] = _send_webhook(payload)
    except Exception as error:
        result["error"] = f"Webhook: {error}"
    try:
        result["serial_message"] = _send_serial(vehicle, owner_name, action)
    except Exception as error:
        result["error"] = f"Puerto serie: {error}"
    return result


def get_state():
    vehicles = db.get_vehicles()
    return {
        "vehicles": vehicles,
        "active_count": sum(1 for vehicle in vehicles if vehicle["focus_active"]),
    }


def activate_for(person_id: int):
    vehicles = db.get_vehicles()
    for vehicle in vehicles:
        if vehicle["focus_active"]:
            db.log_focus_event(vehicle["id"], vehicle["owner_id"], "off")
    db.set_all_focus_off()
    vehicle = db.get_vehicle_by_owner(person_id)
    person = db.get_person(person_id)
    owner_name = person["name"] if person else ""
    if vehicle:
        db.set_focus_on(vehicle["id"])
        db.log_focus_event(vehicle["id"], person_id, "on")
    else:
        db.log_focus_event(None, person_id, "none")
    delivery = _deliver(vehicle, owner_name, "on" if vehicle else "none")
    return {
        "active": bool(vehicle),
        "vehicle": vehicle,
        "delivery": delivery,
    }


def turn_off_all():
    vehicles = db.get_vehicles()
    for vehicle in vehicles:
        if vehicle["focus_active"]:
            db.log_focus_event(vehicle["id"], vehicle["owner_id"], "off")
    db.set_all_focus_off()
    delivery = _deliver(None, "", "off")
    return {"active": False, "delivery": delivery}
