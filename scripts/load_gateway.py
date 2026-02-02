# ============================================
# SCRIPT: Load Testing (Prueba de Carga)
# ============================================
# Simula múltiples usuarios haciendo peticiones simultáneas al gateway.
# PROPÓSITO: Probar el comportamiento bajo alta concurrencia
#
# QUÉ PRUEBA:
# - El semáforo del gateway (MAX_INFLIGHT)
# - Respuesta del sistema bajo carga
# - Cuántas peticiones se procesan exitosamente
# - Cuántas reciben HTTP 429 (Too Many Requests)
# - Cuántas fallan por timeouts u otros errores

import argparse
import concurrent.futures  # Para ejecutar múltiples threads en paralelo
import json
import time

import requests


# FUNCIÓN: Hacer una petición de reserva
def make_request(index, url):
    """
    Simula un usuario haciendo una reserva.
    
    Parámetros:
    - index: Identificador único del usuario simulado
    - url: Endpoint del API Gateway
    
    Retorna:
    - (status_code, response_json) si tuvo éxito
    - ("error", error_message) si falló
    """
    # Payload de la reserva (simulando un usuario diferente cada vez)
    payload = {
        "user_id": f"user-{index}",  # user-0, user-1, user-2, ...
        "event_id": "concert-01",
        "quantity": 1,
        "price": 50,
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code, response.json()
    except Exception as exc:  # noqa: BLE001 - demo script
        # Capturar cualquier error (timeout, conexión rechazada, etc.)
        return "error", str(exc)


# FUNCIÓN PRINCIPAL: Ejecutar la prueba de carga
def main():
    """
    CONFIGURACIÓN:
    --url: Endpoint a probar (default: gateway local)
    --requests: Número total de peticiones a enviar (default: 50)
    --workers: Número de threads concurrentes (default: 10)
    
    EJEMPLO DE USO:
    python load_gateway.py --requests 100 --workers 20
    
    Esto enviaría 100 peticiones usando 20 threads en paralelo
    """
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000/api/reserve")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    # Registrar tiempo de inicio
    started = time.time()
    results = []
    
    # PATRÓN: ThreadPoolExecutor - Ejecutar múltiples peticiones en paralelo
    # max_workers=10 significa que habrá hasta 10 threads ejecutándose simultáneamente
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Crear 50 tareas (futures) que se ejecutarán en los 10 workers
        futures = [executor.submit(make_request, i, args.url) for i in range(args.requests)]
        
        # Esperar a que todas las tareas completen y recoger resultados
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Calcular tiempo total transcurrido
    elapsed = time.time() - started
    
    # Sumarizar resultados por código de estado
    # Ejemplo: {200: 45, 429: 3, "error": 2}
    summary = {}
    for status, _ in results:
        summary[status] = summary.get(status, 0) + 1

    # Imprimir resultados en formato JSON
    print(json.dumps({"elapsed": elapsed, "summary": summary}, indent=2))


# Punto de entrada del script
if __name__ == "__main__":
    main()