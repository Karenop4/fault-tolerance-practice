# ============================================
# SCRIPT: Prueba de Race Condition (Condición de Carrera)
# ============================================
# Demuestra un problema clásico de concurrencia en sistemas distribuidos.
#
# ESCENARIO:
# 1. Resetear el inventario a solo 1 asiento disponible
# 2. Lanzar 2 peticiones simultáneas para reservar ese asiento
# 3. PREGUNTA: ¿Qué debería pasar?
#    - ESPERADO: 1 reserva exitosa, 1 rechazada (no hay asientos)
#    - SIN LOCK: Ambas podrían tener éxito (sobreventa - race condition)
#
# QUÉ PRUEBA:
# - La efectividad del lock (_lock) en el servicio de inventario
# - Si hay race conditions en el sistema

import concurrent.futures  # Para ejecutar peticiones en paralelo
import json

import requests

# URLs de los endpoints
INVENTORY_RESET_URL = "http://localhost:5002/admin/reset"
RESERVE_URL = "http://localhost:5000/api/reserve"

# Payload de la reserva (el mismo para ambas peticiones)
payload = {
    "user_id": "race-user",
    "event_id": "concert-02",
    "quantity": 1,
    "price": 80,
}


# FUNCIÓN PRINCIPAL: Ejecutar la prueba de race condition
def main():
    """
    FLUJO DE LA PRUEBA:
    1. Resetear inventario a 1 asiento
    2. Enviar 2 peticiones EXACTAMENTE al mismo tiempo
    3. Analizar resultados
    
    RESULTADOS ESPERADOS (con lock funcionando correctamente):
    - Primera petición: HTTP 200 (reserva exitosa)
    - Segunda petición: HTTP 409 (no hay asientos disponibles)
    
    RESULTADOS SI HAY RACE CONDITION (sin lock):
    - Ambas peticiones: HTTP 200 (sobreventa - ¡problema grave!)
    """
    
    # PASO 1: Resetear inventario a exactamente 1 asiento
    print("Reseteando inventario a 1 asiento...")
    requests.post(INVENTORY_RESET_URL, json={"event_id": "concert-02", "seats": 1}, timeout=3)

    # PASO 2: Enviar 2 peticiones de reserva EN PARALELO
    # Usamos ThreadPoolExecutor con 2 workers para maximizar la probabilidad de race condition
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Crear 2 futures que se ejecutarán simultáneamente
        futures = [executor.submit(requests.post, RESERVE_URL, json=payload, timeout=5) for _ in range(2)]
        
        # Recoger resultados
        results = []
        for future in futures:
            response = future.result()
            results.append({"status": response.status_code, "body": response.json()})

    # PASO 3: Mostrar resultados
    print(json.dumps(results, indent=2))
    
    # ANALIZAR RESULTADOS:
    status_codes = [r["status"] for r in results]
    if status_codes.count(200) > 1:
        print("\n¡RACE CONDITION DETECTADA! Múltiples reservas exitosas para 1 asiento.")
    elif 200 in status_codes and 409 in status_codes:
        print("\n✓ Funcionamiento correcto: Una reserva exitosa, una rechazada.")
    else:
        print(f"\nResultado inesperado: {status_codes}")


# Punto de entrada del script
if __name__ == "__main__":
    main()