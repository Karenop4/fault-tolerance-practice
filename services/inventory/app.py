import threading

from flask import Flask, jsonify, request

app = Flask(__name__)

_lock = threading.Lock()

# Inventario inicial por evento (memoria).
SEATS = {
    "concert-01": 5,
    "concert-02": 3,
}

CHAOS_FLAGS = {
    "crash": False,
}


def _error(message, status=503):
    return jsonify({"status": "error", "message": message}), status


@app.route("/reserve", methods=["POST"])
def reserve():
    if CHAOS_FLAGS["crash"]:
        return _error("Servicio de Inventario caído (simulado).", 503)

    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    quantity = int(payload.get("quantity", 1))

    # Lock para evitar condiciones de carrera al descontar el último asiento.
    with _lock:
        available = SEATS.get(event_id, 0)
        if available < quantity:
            return _error("No hay asientos disponibles.", 409)
        SEATS[event_id] = available - quantity

    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


@app.route("/release", methods=["POST"])
def release():
    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    quantity = int(payload.get("quantity", 1))

    with _lock:
        SEATS[event_id] = SEATS.get(event_id, 0) + quantity
    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


@app.route("/admin/reset", methods=["POST"])
def reset():
    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    seats = int(payload.get("seats", 1))
    with _lock:
        SEATS[event_id] = seats
    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


@app.route("/chaos/crash", methods=["POST"])
def crash():
    payload = request.get_json(force=True)
    CHAOS_FLAGS["crash"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "crash": CHAOS_FLAGS["crash"]}), 200


@app.route("/health")
def health():
    return jsonify({"status": "ok", "seats": SEATS})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
