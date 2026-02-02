import os
import threading
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

RESERVATIONS_URL = os.getenv("RESERVATIONS_URL", "http://localhost:5001")
MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT", "5"))

# El semáforo limita las solicitudes concurrentes para evitar saturar el gateway.
_inflight_semaphore = threading.BoundedSemaphore(MAX_INFLIGHT)


def _service_unavailable(message, status=503):
    return jsonify({"status": "error", "message": message}), status


@app.route("/")
def index():
    return render_template("index.html", timestamp=datetime.utcnow().isoformat())


@app.route("/api/reserve", methods=["POST"])
def reserve():
    if not _inflight_semaphore.acquire(blocking=False):
        return _service_unavailable(
            "API Gateway saturado: demasiadas solicitudes en vuelo.", status=429
        )

    try:
        # Reenviamos la petición al servicio core de reservas con timeout.
        payload = request.get_json(force=True)
        response = requests.post(
            f"{RESERVATIONS_URL}/reserve",
            json=payload,
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.Timeout:
        return _service_unavailable(
            "Tiempo de espera agotado en el Servicio de Reservas.", status=504
        )
    except requests.RequestException as exc:
        return _service_unavailable(
            f"No se pudo contactar al Servicio de Reservas: {exc}.", status=503
        )
    finally:
        _inflight_semaphore.release()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
