import time

from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuración de caos: latencia artificial y fallos forzados.
CHAOS_FLAGS = {
    "latency_seconds": 0,
    "fail": False,
}


def _error(message, status=503):
    return jsonify({"status": "error", "message": message}), status


@app.route("/pay", methods=["POST"])
def pay():
    payload = request.get_json(force=True)
    # Simulamos un proveedor lento durmiendo varios segundos.
    if CHAOS_FLAGS["latency_seconds"] > 0:
        time.sleep(CHAOS_FLAGS["latency_seconds"])
    if CHAOS_FLAGS["fail"]:
        return _error("Pago rechazado por el proveedor (simulado).", 502)

    return (
        jsonify(
            {
                "status": "ok",
                "message": "Pago aprobado.",
                "amount": payload.get("price", 0) * payload.get("quantity", 1),
            }
        ),
        200,
    )


@app.route("/chaos/latency", methods=["POST"])
def chaos_latency():
    payload = request.get_json(force=True)
    CHAOS_FLAGS["latency_seconds"] = int(payload.get("seconds", 0))
    return jsonify({"status": "ok", "latency": CHAOS_FLAGS["latency_seconds"]}), 200


@app.route("/chaos/fail", methods=["POST"])
def chaos_fail():
    payload = request.get_json(force=True)
    CHAOS_FLAGS["fail"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "fail": CHAOS_FLAGS["fail"]}), 200


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
