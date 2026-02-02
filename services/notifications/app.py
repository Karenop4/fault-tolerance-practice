from flask import Flask, jsonify, request

app = Flask(__name__)

# Permite simular la caída total del servicio de notificaciones.
CHAOS_FLAGS = {
    "down": False,
}


def _error(message, status=503):
    return jsonify({"status": "error", "message": message}), status


@app.route("/send", methods=["POST"])
def send():
    if CHAOS_FLAGS["down"]:
        return _error("Servicio de notificaciones inactivo (simulado).", 503)
    payload = request.get_json(force=True)
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Correo enviado.",
                "user_id": payload.get("user_id"),
            }
        ),
        200,
    )


@app.route("/chaos/down", methods=["POST"])
def down():
    payload = request.get_json(force=True)
    CHAOS_FLAGS["down"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "down": CHAOS_FLAGS["down"]}), 200


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
