import os
import random
import sqlite3
import time
from datetime import datetime

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5002")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://localhost:5003")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://localhost:5004")
DB_PATH = os.getenv("DB_PATH", "reservations.db")

# Bandera de caos para simular fallos intermitentes en la base de datos.
CHAOS_FLAGS = {
    "db_flapping": False,
}


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@app.before_first_request
def startup():
    init_db()


def save_reservation(payload, retries=3, delay=0.3):
    last_error = None
    # Reintentamos para simular un patrón simple de resiliencia.
    for attempt in range(1, retries + 1):
        try:
            if CHAOS_FLAGS["db_flapping"] and random.random() < 0.5:
                raise sqlite3.OperationalError("DB flapping: conexión intermitente")

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT INTO reservations (user_id, event_id, quantity, price, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        payload["user_id"],
                        payload["event_id"],
                        payload["quantity"],
                        payload["price"],
                        datetime.utcnow().isoformat(),
                    ),
                )
                conn.commit()
            return True, None
        except sqlite3.Error as exc:
            last_error = str(exc)
            time.sleep(delay)
    return False, last_error


def notify_user(payload):
    try:
        response = requests.post(
            f"{NOTIFICATIONS_URL}/send", json=payload, timeout=2
        )
        if response.status_code >= 400:
            return False, response.json().get("message", "Fallo al notificar")
        return True, None
    except requests.RequestException as exc:
        return False, str(exc)


@app.route("/reserve", methods=["POST"])
def reserve():
    payload = request.get_json(force=True)
    payload.setdefault("quantity", 1)

    # 1) Reservar inventario (si falla, abortamos temprano).
    try:
        inventory_response = requests.post(
            f"{INVENTORY_URL}/reserve", json=payload, timeout=2
        )
        if inventory_response.status_code >= 400:
            return (
                jsonify(inventory_response.json()),
                inventory_response.status_code,
            )
    except requests.RequestException as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Inventario no disponible: {exc}.",
                }
            ),
            503,
        )

    # 2) Procesar pago (si falla, liberamos inventario).
    try:
        payment_response = requests.post(
            f"{PAYMENTS_URL}/pay", json=payload, timeout=3
        )
        if payment_response.status_code >= 400:
            _release_inventory(payload)
            return (
                jsonify(payment_response.json()),
                payment_response.status_code,
            )
    except requests.Timeout:
        _release_inventory(payload)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Pago tardó demasiado y fue cancelado.",
                }
            ),
            504,
        )
    except requests.RequestException as exc:
        _release_inventory(payload)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Servicio de pagos no disponible: {exc}.",
                }
            ),
            503,
        )

    # 3) Persistir en la base de datos con reintentos.
    saved, error = save_reservation(payload)
    if not saved:
        _release_inventory(payload)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"No se pudo guardar la reserva: {error}.",
                }
            ),
            503,
        )

    # 4) Notificar al usuario (fallo no crítico).
    notified, notice_error = notify_user(payload)

    return (
        jsonify(
            {
                "status": "ok",
                "message": "Reserva confirmada.",
                "notification": {
                    "sent": notified,
                    "details": notice_error,
                },
            }
        ),
        200,
    )


def _release_inventory(payload):
    try:
        requests.post(f"{INVENTORY_URL}/release", json=payload, timeout=2)
    except requests.RequestException:
        pass


@app.route("/chaos/db_flap", methods=["POST"])
def toggle_db_flap():
    body = request.get_json(force=True)
    CHAOS_FLAGS["db_flapping"] = bool(body.get("enabled", False))
    return jsonify({"status": "ok", "db_flapping": CHAOS_FLAGS["db_flapping"]})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001)
