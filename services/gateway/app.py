# ============================================
# SERVICIO GATEWAY - API Gateway Principal
# ============================================
# Este es el punto de entrada de la aplicación.
# Recibe peticiones HTTP de los clientes y las reenvía al servicio de Reservations.
# PATRÓN: API Gateway - centraliza el acceso y aplica límites de concurrencia

import os
import threading
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# CONFIGURACIÓN: URLs de los servicios backend y límites de concurrencia
RESERVATIONS_URL = os.getenv("RESERVATIONS_URL", "http://localhost:5001")
MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT", "5"))  # Máximo de peticiones simultáneas permitidas

# PATRÓN: Semáforo (BoundedSemaphore) - Controla la concurrencia
# Limita el número de solicitudes que pueden procesarse al mismo tiempo
# Esto evita saturar el gateway y proporciona backpressure (contrapresión)
_inflight_semaphore = threading.BoundedSemaphore(MAX_INFLIGHT)


# FUNCIÓN AUXILIAR: Genera respuestas de error estandarizadas
def _service_unavailable(message, status=503):
    """Retorna un JSON de error con el código de estado HTTP especificado"""
    return jsonify({"status": "error", "message": message}), status


# ENDPOINT: Página principal (interfaz web)
@app.route("/")
def index():
    """Renderiza la página HTML con un timestamp para mostrar la interfaz de usuario"""
    return render_template("index.html", timestamp=datetime.utcnow().isoformat())


# ENDPOINT PRINCIPAL: Crear una reserva
@app.route("/api/reserve", methods=["POST"])
def reserve():
    """
    LÓGICA DE TOLERANCIA A FALLOS:
    1. Control de concurrencia con semáforo (evita sobrecarga)
    2. Timeout en las peticiones (evita bloqueos indefinidos)
    3. Manejo de excepciones (degrada gracefully)
    """
    
    # PASO 1: Verificar si podemos procesar la solicitud (control de tráfico)
    # acquire(blocking=False) intenta obtener el semáforo sin bloquear
    # Si devuelve False, significa que ya hay MAX_INFLIGHT solicitudes en proceso
    if not _inflight_semaphore.acquire(blocking=False):
        # HTTP 429 = Too Many Requests - el cliente debe reintentar después
        return _service_unavailable(
            "API Gateway saturado: demasiadas solicitudes en vuelo.", status=429
        )

    try:
        # PASO 2: Extraer el payload JSON de la petición
        payload = request.get_json(force=True)
        
        # PASO 3: Reenviar la petición al servicio de reservas (proxy)
        # TIMEOUT de 5 segundos - evita esperar indefinidamente
        # Esto es crucial para no bloquear recursos del gateway
        response = requests.post(
            f"{RESERVATIONS_URL}/reserve",
            json=payload,
            timeout=5,
        )
        # Devolver la misma respuesta que recibimos del servicio backend
        return jsonify(response.json()), response.status_code
        
    except requests.Timeout:
        # CASO 1: El servicio tardó más de 5 segundos en responder
        # HTTP 504 = Gateway Timeout
        return _service_unavailable(
            "Tiempo de espera agotado en el Servicio de Reservas.", status=504
        )
        
    except requests.RequestException as exc:
        # CASO 2: Cualquier otro error de red (servicio caído, conexión rechazada, etc.)
        # HTTP 503 = Service Unavailable
        return _service_unavailable(
            f"No se pudo contactar al Servicio de Reservas: {exc}.", status=503
        )
        
    finally:
        # IMPORTANTE: Siempre liberamos el semáforo, sin importar si hubo error
        # Esto asegura que no perdemos "slots" de concurrencia
        _inflight_semaphore.release()


# ENDPOINT: Health check
@app.route("/health")
def health():
    """Verifica que el servicio esté funcionando (usado por orquestadores como Kubernetes)"""
    return jsonify({"status": "ok"})


# PUNTO DE ENTRADA: Inicia el servidor Flask
if __name__ == "__main__":
    # host="0.0.0.0" permite conexiones desde cualquier IP (necesario en Docker)
    # port=5000 es el puerto donde escucha el gateway
    app.run(host="0.0.0.0", port=5000)
