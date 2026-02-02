# ============================================
# SERVICIO RESERVATIONS - Orquestador Principal
# ============================================
# Este es el servicio más complejo - actúa como ORQUESTADOR de la transacción distribuida.
# PATRÓN: Saga Pattern (Orquestación)
# Coordina múltiples servicios para completar una reserva:
# 1. Inventory (reservar asientos)
# 2. Payments (procesar pago)
# 3. Base de datos local (persistir reserva)
# 4. Notifications (notificar usuario - opcional)
#
# TOLERANCIA A FALLOS IMPLEMENTADA:
# - Retry logic (reintentos) para la base de datos
# - Compensating transactions (rollback de inventario si falla el pago)
# - Timeouts para evitar bloqueos indefinidos
# - Degradación graciosa (la notificación puede fallar sin cancelar la reserva)

import os
import random
import sqlite3
import time
from datetime import datetime

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# CONFIGURACIÓN: URLs de los servicios dependientes
# Estas se configuran mediante variables de entorno en Docker Compose
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5002")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://localhost:5003")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://localhost:5004")
DB_PATH = os.getenv("DB_PATH", "reservations.db")  # Ruta de la base de datos SQLite

# CHAOS ENGINEERING: Simular problemas con la base de datos
# db_flapping: Conexión intermitente (50% de fallos aleatorios)
CHAOS_FLAGS = {
    "db_flapping": False,  # Simula una BD inestable
}


# FUNCIÓN: Inicializar la base de datos SQLite
def init_db():
    """
    Crea la tabla de reservations si no existe.
    SQLite es una base de datos embebida (archivo local) - simple pero útil para demos.
    En producción usarías PostgreSQL, MySQL, etc.
    """
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


# Inicializar la BD al arrancar el servicio
init_db()


# FUNCIÓN: Guardar reserva en la BD con reintentos
def save_reservation(payload, retries=3, delay=0.3):
    """
    PATRÓN: Retry Logic (Lógica de reintentos)
    Intenta guardar la reserva hasta 3 veces antes de fallar.
    
    POR QUÉ ES NECESARIO:
    - Fallos transitorios de red
    - Bloqueos temporales de la BD (locks)
    - Problemas momentáneos de I/O
    
    ESTRATEGIA:
    - Exponential backoff podría usarse (aumentar el delay en cada intento)
    - Aquí usamos delay fijo de 0.3 segundos
    
    RETORNA:
    - (True, None) si tuvo éxito
    - (False, error_message) si falló después de todos los reintentos
    """
    last_error = None
    
    # Intentar hasta 'retries' veces
    for attempt in range(1, retries + 1):
        try:
            # CHAOS SIMULATION: Fallos aleatorios de BD
            # 50% de probabilidad de fallo si db_flapping está activo
            if CHAOS_FLAGS["db_flapping"] and random.random() < 0.5:
                raise sqlite3.OperationalError("DB flapping: conexión intermitente")

            # Intentar guardar en la base de datos
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
            # Si llegamos aquí, la operación tuvo éxito
            return True, None
            
        except sqlite3.Error as exc:
            # Capturar el error y guardarlo
            last_error = str(exc)
            # Esperar antes de reintentar (dar tiempo a que se resuelva el problema)
            time.sleep(delay)
    
    # Si llegamos aquí, todos los reintentos fallaron
    return False, last_error


# FUNCIÓN: Notificar al usuario
def notify_user(payload):
    """
    Intenta enviar una notificación al usuario.
    
    IMPORTANTE: Esta operación es NO CRÍTICA
    - Si falla, la reserva sigue siendo válida
    - Se reporta el estado en la respuesta pero no se hace rollback
    
    TIMEOUT: 2 segundos - evita esperar demasiado por un servicio no esencial
    
    RETORNA:
    - (True, None) si la notificación se envió exitosamente
    - (False, error_message) si falló
    """
    try:
        response = requests.post(
            f"{NOTIFICATIONS_URL}/send", json=payload, timeout=2
        )
        if response.status_code >= 400:
            return False, response.json().get("message", "Fallo al notificar")
        return True, None
    except requests.RequestException as exc:
        # Cualquier error de red o timeout
        return False, str(exc)


# ============================================
# ENDPOINT PRINCIPAL: Crear una reserva
# ============================================
# Este es el corazón del sistema - implementa una TRANSACCIÓN DISTRIBUIDA
# PATRÓN: Saga Pattern con Compensating Transactions
@app.route("/reserve", methods=["POST"])
def reserve():
    """
    FLUJO DE LA TRANSACCIÓN DISTRIBUIDA (4 pasos):
    1. Reservar inventario (crítico - falla rápido)
    2. Procesar pago (crítico - rollback si falla)
    3. Guardar en BD (crítico - rollback si falla)
    4. Notificar usuario (no crítico - best effort)
    
    GARANTÍAS:
    - Atomicidad parcial: Si cualquier paso crítico falla, se hace rollback
    - Consistencia: No se cobra sin reservar, no se reserva sin persistir
    - Tolerancia a fallos: Reintentos, timeouts, compensating transactions
    """
    
    # Extraer datos de la petición
    payload = request.get_json(force=True)
    payload.setdefault("quantity", 1)  # Por defecto 1 asiento

    # ========================================
    # PASO 1: Reservar inventario
    # ========================================
    # ESTRATEGIA: Fail-fast (fallar rápido)
    # Si no hay inventario, no tiene sentido continuar
    try:
        inventory_response = requests.post(
            f"{INVENTORY_URL}/reserve", 
            json=payload, 
            timeout=2  # Timeout corto - debe ser rápido
        )
        # Si el inventario responde con error (ej: no hay asientos)
        if inventory_response.status_code >= 400:
            # Propagar el error directamente al cliente
            return (
                jsonify(inventory_response.json()),
                inventory_response.status_code,
            )
    except requests.RequestException as exc:
        # Fallo de red/comunicación con el servicio de inventario
        # HTTP 503 = Service Unavailable
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Inventario no disponible: {exc}.",
                }
            ),
            503,
        )

    # ========================================
    # PASO 2: Procesar pago
    # ========================================
    # CRÍTICO: Si falla, DEBEMOS liberar el inventario (compensating transaction)
    try:
        payment_response = requests.post(
            f"{PAYMENTS_URL}/pay", 
            json=payload, 
            timeout=3  # Timeout más largo - el pago puede tardar
        )
        # Si el pago fue rechazado (tarjeta inválida, fondos insuficientes, etc.)
        if payment_response.status_code >= 400:
            # COMPENSATING TRANSACTION: Devolver los asientos al inventario
            _release_inventory(payload)
            return (
                jsonify(payment_response.json()),
                payment_response.status_code,
            )
    except requests.Timeout:
        # El servicio de pagos tardó demasiado (>3 segundos)
        # IMPORTANTE: No sabemos si el pago se procesó o no
        # DECISIÓN: Cancelar la reserva por seguridad
        _release_inventory(payload)
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Pago tardó demasiado y fue cancelado.",
                }
            ),
            504,  # Gateway Timeout
        )
    except requests.RequestException as exc:
        # Cualquier otro error de red con el servicio de pagos
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

    # ========================================
    # PASO 3: Persistir en la base de datos
    # ========================================
    # CRÍTICO: Si no podemos guardar, debemos hacer rollback completo
    # La función save_reservation incluye retry logic (3 intentos)
    saved, error = save_reservation(payload)
    if not saved:
        # COMPENSATING TRANSACTION: Liberar inventario
        # NOTA: El dinero ya fue cobrado - en un sistema real habría que hacer refund
        # Esta es una limitación de las transacciones distribuidas (eventual consistency)
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

    # ========================================
    # PASO 4: Notificar al usuario
    # ========================================
    # NO CRÍTICO: Si falla, la reserva sigue siendo válida
    # PATRÓN: Best Effort - intentamos pero no nos bloqueamos en el error
    notified, notice_error = notify_user(payload)

    # ========================================
    # RESPUESTA EXITOSA
    # ========================================
    # Todos los pasos críticos completados exitosamente
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Reserva confirmada.",
                "notification": {
                    "sent": notified,  # True/False
                    "details": notice_error,  # None o mensaje de error
                },
            }
        ),
        200,
    )


# FUNCIÓN AUXILIAR: Liberar inventario (Compensating Transaction)
def _release_inventory(payload):
    """
    PATRÓN: Compensating Transaction
    Revierte la reserva de inventario cuando falla un paso posterior.
    
    IMPORTANTE:
    - Esta operación NO debe fallar, pero si lo hace, lo ignoramos
    - En producción, deberías logear este error y tener un proceso de reconciliación
    - Esto puede causar inconsistencias temporales (asientos bloqueados)
    
    ESCENARIOS DE USO:
    - El pago falló/timeoutó
    - No se pudo guardar en la BD
    """
    try:
        requests.post(f"{INVENTORY_URL}/release", json=payload, timeout=2)
    except requests.RequestException:
        # Ignoramos el error - no hay mucho más que podamos hacer aquí
        # En producción: logear y posiblemente enviar a una cola de reintentos
        pass


# ENDPOINT CHAOS: Simular problemas con la base de datos
@app.route("/chaos/db_flap", methods=["POST"])
def toggle_db_flap():
    """
    Activa/desactiva la simulación de una base de datos inestable.
    Útil para probar la retry logic.
    
    Cuando está activo:
    - 50% de probabilidad de fallo en cada operación de BD
    - Fuerza al sistema a usar los reintentos
    """
    body = request.get_json(force=True)
    CHAOS_FLAGS["db_flapping"] = bool(body.get("enabled", False))
    return jsonify({"status": "ok", "db_flapping": CHAOS_FLAGS["db_flapping"]})


# ENDPOINT: Health check
@app.route("/health")
def health():
    """Verifica que el servicio esté activo"""
    return jsonify({"status": "ok"})


# PUNTO DE ENTRADA: Inicia el servidor Flask en el puerto 5001
if __name__ == "__main__":
    # Asegurar que la BD esté inicializada antes de arrancar
    init_db()
    app.run(host="0.0.0.0", port=5001)
