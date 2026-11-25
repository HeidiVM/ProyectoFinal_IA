import sqlite3
from contextlib import contextmanager
from datetime import datetime

try:
    from . import config
except ImportError:
    import config

DB_PATH = config.DB_PATH
ensure_dirs = config.ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL UNIQUE,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    color TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    focus_active INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES people(id)
);

CREATE TABLE IF NOT EXISTS face_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS focus_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER,
    person_id INTEGER,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

PEOPLE = [
    "Alexander Luisa",
    "Alex Guachi",
    "Heidi Villavicenicio",
    "Steven Toala",
]

VEHICLES = [
    ("ABC-1234", "Toyota", "Corolla", "Blanco", "Alexander Luisa"),
    ("XYZ-5678", "Honda", "Civic", "Gris", "Alex Guachi"),
    ("JKL-9012", "Mazda", "CX-5", "Rojo", "Heidi Villavicenicio"),
    ("MNP-3456", "Chevrolet", "Tracker", "Negro", "Steven Toala"),
]


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    ensure_dirs()
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        existing = connection.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        if existing:
            return
        for name in PEOPLE:
            connection.execute("INSERT INTO people (name) VALUES (?)", (name,))
        for plate, brand, model, color, owner_name in VEHICLES:
            owner = connection.execute(
                "SELECT id FROM people WHERE name = ?", (owner_name,)
            ).fetchone()
            connection.execute(
                "INSERT INTO vehicles (plate, brand, model, color, owner_id) VALUES (?, ?, ?, ?, ?)",
                (plate, brand, model, color, owner["id"]),
            )


def get_people():
    with get_connection() as connection:
        rows = connection.execute("SELECT id, name FROM people ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_person(person_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name FROM people WHERE id = ?", (person_id,)
        ).fetchone()
    return dict(row) if row else None


def get_vehicles():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT v.id, v.plate, v.brand, v.model, v.color,
                   v.owner_id, p.name AS owner_name,
                   v.focus_active, v.updated_at
            FROM vehicles v
            JOIN people p ON p.id = v.owner_id
            ORDER BY v.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_vehicle(vehicle_id: int):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT v.id, v.plate, v.brand, v.model, v.color,
                   v.owner_id, p.name AS owner_name,
                   v.focus_active, v.updated_at
            FROM vehicles v
            JOIN people p ON p.id = v.owner_id
            WHERE v.id = ?
            """,
            (vehicle_id,),
        ).fetchone()
    return dict(row) if row else None


def get_vehicle_by_owner(person_id: int):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT v.id, v.plate, v.brand, v.model, v.color,
                   v.owner_id, p.name AS owner_name,
                   v.focus_active, v.updated_at
            FROM vehicles v
            JOIN people p ON p.id = v.owner_id
            WHERE v.owner_id = ?
            ORDER BY v.id
            LIMIT 1
            """,
            (person_id,),
        ).fetchone()
    return dict(row) if row else None


def set_vehicle_owner(vehicle_id: int, owner_id: int):
    with get_connection() as connection:
        vehicle = connection.execute(
            "SELECT id FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            return None
        owner = connection.execute(
            "SELECT id FROM people WHERE id = ?", (owner_id,)
        ).fetchone()
        if not owner:
            raise ValueError("La persona seleccionada no existe")
        connection.execute(
            "UPDATE vehicles SET owner_id = ?, updated_at = ? WHERE id = ?",
            (owner_id, datetime.utcnow().isoformat(timespec="seconds"), vehicle_id),
        )
    return get_vehicle(vehicle_id)


def set_all_focus_off() -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE vehicles SET focus_active = 0 WHERE focus_active <> 0"
        )


def set_focus_on(vehicle_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE vehicles SET focus_active = 0 WHERE focus_active <> 0"
        )
        connection.execute(
            "UPDATE vehicles SET focus_active = 1, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), vehicle_id),
        )


def log_focus_event(vehicle_id, person_id, action: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO focus_events (vehicle_id, person_id, action) VALUES (?, ?, ?)",
            (vehicle_id, person_id, action),
        )


def add_face_sample(person_id: int, image_path: str) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO face_samples (person_id, image_path) VALUES (?, ?)",
            (person_id, image_path),
        )
        return int(cursor.lastrowid)


def get_face_samples():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, person_id, image_path FROM face_samples ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_face_status():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.name, COUNT(f.id) AS sample_count
            FROM people p
            LEFT JOIN face_samples f ON f.person_id = p.id
            GROUP BY p.id, p.name
            ORDER BY p.id
            """
        ).fetchall()
    return [dict(row) for row in rows]
