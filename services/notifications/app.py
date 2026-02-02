# ============================================
# SERVICIO NOTIFICATIONS - Envío de Notificaciones
# ============================================
# Servicio auxiliar que simula el envío de emails/notificaciones.
# CARACTERÍSTICA: Es un servicio NO CRÍTICO (si falla, la reserva sigue siendo válida)
# PATRÓN: Fire and forget con manejo de fallos opcional

from flask import Flask, jsonify, request

app = Flask(__name__)

# CHAOS ENGINEERING: Simular servicio completamente inactivo
# Permite probar la resiliencia cuando este servicio no está disponible
CHAOS_FLAGS = {
    "down": False,  # Si es True, todas las peticiones fallan
}


# FUNCIÓN AUXILIAR: Genera respuestas de error
def _error(message, status=503):
    """Retorna un JSON de error con código HTTP especificado"""
    return jsonify({"status": "error", "message": message}), status


# ENDPOINT: Enviar notificación al usuario
@app.route("/send", methods=["POST"])
def send():
    """
    Simula el envío de un correo electrónico.
    IMPORTANTE: Este servicio es NO CRÍTICO - si falla, no se cancela la reserva.
    La lógica del servicio de reservations maneja el fallo gracefully.
    """
    
    # CHAOS SIMULATION: Simular servicio inactivo
    if CHAOS_FLAGS["down"]:
        return _error("Servicio de notificaciones inactivo (simulado).", 503)
    
    # Extraer datos del usuario para enviar la notificación
    payload = request.get_json(force=True)
    
    # En un sistema real, aquí se enviaría un email usando SendGrid, AWS SES, etc.
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


# ENDPOINT CHAOS: Activar/desactivar simulación de servicio caído
@app.route("/chaos/down", methods=["POST"])
def down():
    """Permite probar cómo el sistema maneja la indisponibilidad de notificaciones"""
    payload = request.get_json(force=True)
    CHAOS_FLAGS["down"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "down": CHAOS_FLAGS["down"]}), 200


# ENDPOINT: Health check
@app.route("/health")
def health():
    """Verifica que el servicio esté activo"""
    return jsonify({"status": "ok"})


# PUNTO DE ENTRADA: Inicia el servidor en el puerto 5004
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
