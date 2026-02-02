# ============================================
# SERVICIO INVENTORY - Gestión de Inventario
# ============================================
# Maneja la disponibilidad de asientos para eventos.
# PATRÓN: State Management con sincronización mediante locks

import threading

from flask import Flask, jsonify, request

app = Flask(__name__)

# PATRÓN: Lock (Mutex) - Sincronización de threads
# Evita condiciones de carrera cuando múltiples threads acceden al inventario
# PROBLEMA SIN LOCK: Dos threads pueden leer available=1 simultáneamente y ambos reservar
_lock = threading.Lock()

# ESTRUCTURA DE DATOS: Diccionario en memoria para almacenar inventario
# En producción esto estaría en una base de datos
# Key = event_id, Value = número de asientos disponibles
SEATS = {
    "concert-01": 5,
    "concert-02": 3,
}

# CHAOS ENGINEERING: Banderas para simular fallos
# Permite probar cómo el sistema maneja servicios caídos
CHAOS_FLAGS = {
    "crash": False,  # Si es True, el servicio simula estar caído
}


# FUNCIÓN AUXILIAR: Genera respuestas de error estandarizadas
def _error(message, status=503):
    """Retorna un JSON de error con el código HTTP especificado"""
    return jsonify({"status": "error", "message": message}), status


# ENDPOINT: Reservar asientos (decrementar inventario)
@app.route("/reserve", methods=["POST"])
def reserve():
    """
    LÓGICA CRÍTICA: Operación atómica de lectura-verificación-escritura
    Esta es una sección crítica que DEBE protegerse con locks
    """
    
    # CHAOS SIMULATION: Si la bandera está activa, simular servicio caído
    if CHAOS_FLAGS["crash"]:
        return _error("Servicio de Inventario caído (simulado).", 503)

    # Extraer datos de la petición
    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    quantity = int(payload.get("quantity", 1))

    # SECCIÓN CRÍTICA: Debe ejecutarse de forma atómica
    # El 'with _lock' asegura que solo un thread ejecute este bloque a la vez
    # PROBLEMA DE RACE CONDITION:
    # Thread A lee available=1
    # Thread B lee available=1 (antes de que A escriba)
    # Ambos piensan que hay disponibilidad y reservan -> sobreventa
    with _lock:
        # PASO 1: Leer inventario actual
        available = SEATS.get(event_id, 0)
        
        # PASO 2: Verificar disponibilidad
        if available < quantity:
            # HTTP 409 = Conflict - no hay suficientes asientos
            return _error("No hay asientos disponibles.", 409)
        
        # PASO 3: Actualizar inventario (decrementar)
        SEATS[event_id] = available - quantity

    # Respuesta exitosa con el inventario restante
    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


# ENDPOINT: Liberar asientos (incrementar inventario)
@app.route("/release", methods=["POST"])
def release():
    """
    PATRÓN: Compensating Transaction (transacción compensatoria)
    Se usa cuando una reserva falla en pasos posteriores (ej: pago rechazado)
    Devuelve los asientos al inventario para mantener consistencia
    """
    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    quantity = int(payload.get("quantity", 1))

    # También protegemos esta operación con lock por consistencia
    with _lock:
        # Incrementar el inventario
        SEATS[event_id] = SEATS.get(event_id, 0) + quantity
    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


# ENDPOINT ADMIN: Resetear inventario de un evento
@app.route("/admin/reset", methods=["POST"])
def reset():
    """Endpoint administrativo para restablecer el inventario a un valor específico"""
    payload = request.get_json(force=True)
    event_id = payload.get("event_id")
    seats = int(payload.get("seats", 1))
    with _lock:
        # Sobrescribir el valor del inventario
        SEATS[event_id] = seats
    return jsonify({"status": "ok", "remaining": SEATS[event_id]}), 200


# ENDPOINT CHAOS: Simular caída del servicio
@app.route("/chaos/crash", methods=["POST"])
def crash():
    """
    CHAOS ENGINEERING: Permite activar/desactivar la simulación de fallo
    Útil para probar cómo otros servicios manejan la indisponibilidad
    """
    payload = request.get_json(force=True)
    CHAOS_FLAGS["crash"] = bool(payload.get("enabled", False))
    return jsonify({"status": "ok", "crash": CHAOS_FLAGS["crash"]}), 200


# ENDPOINT: Health check
@app.route("/health")
def health():
    """Retorna el estado del servicio y el inventario actual"""
    return jsonify({"status": "ok", "seats": SEATS})


# PUNTO DE ENTRADA: Inicia el servidor Flask en el puerto 5002
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
