# ============================================
# SERVICIO PAYMENTS - Procesamiento de Pagos
# ============================================
# Simula la integración con un proveedor de pagos externo (ej: Stripe, PayPal).
# CARACTERÍSTICA: Servicio CRÍTICO - si falla, la reserva debe cancelarse
# PROBLEMAS SIMULADOS: Latencia alta, fallos transitorios

import time

from flask import Flask, jsonify, request

app = Flask(__name__)

# CHAOS ENGINEERING: Simular problemas comunes con proveedores externos
# latency_seconds: Simula un proveedor lento (problema común en producción)
# fail: Simula rechazo del pago por parte del proveedor
CHAOS_FLAGS = {
    "latency_seconds": 0,  # Segundos de delay artificial
    "fail": False,         # Si es True, todos los pagos son rechazados
}


# FUNCIÓN AUXILIAR: Genera respuestas de error
def _error(message, status=503):
    """Retorna un JSON de error con el código HTTP especificado"""
    return jsonify({"status": "error", "message": message}), status


# ENDPOINT: Procesar pago
@app.route("/pay", methods=["POST"])
def pay():
    """
    Simula el procesamiento de un pago con un proveedor externo.
    PROBLEMAS SIMULADOS:
    1. Latencia alta (servicios externos lentos)
    2. Fallos transitorios (rechazos de pago)
    """
    payload = request.get_json(force=True)
    
    # SIMULACIÓN DE LATENCIA: Proveedor de pagos lento
    # En producción, esto puede ocurrir por:
    # - Congestión de red
    # - Sobrecarga del proveedor
    # - Problemas de rendimiento en el API del proveedor
    if CHAOS_FLAGS["latency_seconds"] > 0:
        time.sleep(CHAOS_FLAGS["latency_seconds"])  # Bloquea el thread por N segundos
    
    # SIMULACIÓN DE FALLO: Pago rechazado
    if CHAOS_FLAGS["fail"]:
        # HTTP 502 = Bad Gateway - el servicio externo respondió con error
        return _error("Pago rechazado por el proveedor (simulado).", 502)

    # Calcular el monto total del pago
    amount = payload.get("price", 0) * payload.get("quantity", 1)
    
    # Respuesta exitosa - pago aprobado
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Pago aprobado.",
                "amount": amount,
            }
        ),
        200,
    )


# ENDPOINT CHAOS: Configurar latencia artificial
@app.route("/chaos/latency", methods=["POST"])
def chaos_latency():
    """
    Permite simular un proveedor de pagos lento.
    Útil para probar timeouts y comportamiento bajo latencia alta.
    """
    payload = request.get_json(force=True)
    CHAOS_FLAGS["latency_seconds"] = int(payload.get("seconds", 0))
    return jsonify({"status": "ok", "latency": CHAOS_FLAGS["latency_seconds"]}), 200


# ENDPOINT CHAOS: Forzar fallos en los pagos
@app.route("/chaos/fail", methods=["POST"])
def chaos_fail():
    """
    Permite simular rechazos de pago por parte del proveedor.
    Útil para probar el manejo de errores y rollback de transacciones.
    """
    payload = request.get_json(force=True)
    CHAOS_FLAGS["fail"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "fail": CHAOS_FLAGS["fail"]}), 200


# ENDPOINT: Health check
@app.route("/health")
def health():
    """Verifica que el servicio esté activo"""
    return jsonify({"status": "ok"})


# PUNTO DE ENTRADA: Inicia el servidor en el puerto 5003
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
