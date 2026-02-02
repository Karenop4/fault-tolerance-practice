# 📚 GUÍA DE ESTUDIO - SISTEMAS DISTRIBUIDOS
## Conceptos Clave para tu Examen

Este documento resume todos los patrones, conceptos y técnicas implementadas en este proyecto.

---

## 🏗️ ARQUITECTURA GENERAL

### Patrón: Microservicios
- **5 servicios independientes** comunicándose por HTTP
- Cada servicio tiene su responsabilidad única (Single Responsibility Principle)
- Ventajas: Escalabilidad, despliegue independiente, aislamiento de fallos
- Desventajas: Complejidad en coordinación, latencia de red

### Comunicación entre Servicios
- **Protocolo**: HTTP/REST (síncrono)
- **Formato**: JSON para intercambio de datos
- **Discovery**: Docker DNS (nombres de servicios como hostnames)

---

## 🛡️ PATRONES DE TOLERANCIA A FALLOS

### 1. **API Gateway Pattern**
**Ubicación**: [services/gateway/app.py](services/gateway/app.py)

**Qué es**: Punto de entrada único que centraliza el acceso a los microservicios.

**Beneficios**:
- Control de tráfico centralizado
- Aplicación de políticas (rate limiting, autenticación)
- Simplifica el cliente (una sola URL)

**Implementación**:
```python
# Reenvía peticiones al backend
response = requests.post(f"{RESERVATIONS_URL}/reserve", json=payload)
```

---

### 2. **Semaphore (Control de Concurrencia)**
**Ubicación**: [services/gateway/app.py](services/gateway/app.py#L18)

**Qué es**: Limita el número de peticiones que se procesan simultáneamente.

**Por qué es necesario**:
- Evita sobrecarga del servidor (backpressure)
- Previene agotamiento de recursos (threads, conexiones)
- Protege servicios downstream

**Implementación**:
```python
_inflight_semaphore = threading.BoundedSemaphore(MAX_INFLIGHT)

if not _inflight_semaphore.acquire(blocking=False):
    return error("Saturado"), 429  # Too Many Requests
```

**HTTP 429**: El cliente debe reintentar más tarde (exponential backoff recomendado).

---

### 3. **Timeouts**
**Ubicación**: Múltiples archivos

**Qué es**: Límite de tiempo para esperar respuestas de servicios externos.

**Por qué es crítico**:
- Sin timeouts, un servicio lento puede bloquear todos los recursos
- Permite fallar rápido (fail-fast) y liberar recursos

**Ejemplos en el código**:
```python
# Timeout corto para operaciones rápidas
requests.post(url, json=data, timeout=2)

# Timeout más largo para operaciones costosas
requests.post(url, json=data, timeout=5)
```

**Regla de oro**: Siempre usar timeouts en operaciones de red.

---

### 4. **Lock (Mutex) para Race Conditions**
**Ubicación**: [services/inventory/app.py](services/inventory/app.py#L15)

**Problema - Race Condition**:
```
Thread A lee: available=1
Thread B lee: available=1  ← antes de que A escriba
Thread A escribe: available=0
Thread B escribe: available=0  ← ¡Sobreventa! Ambos reservaron
```

**Solución - Lock**:
```python
with _lock:  # Solo un thread puede entrar a la vez
    available = SEATS.get(event_id, 0)
    if available < quantity:
        return error("No disponible")
    SEATS[event_id] = available - quantity  # Operación atómica
```

**Operaciones que necesitan locks**:
- Lectura-modificación-escritura (read-modify-write)
- Incrementos/decrementos de contadores compartidos
- Cualquier operación que NO sea atómica

---

### 5. **Retry Logic (Lógica de Reintentos)**
**Ubicación**: [services/reservations/app.py](services/reservations/app.py#L48)

**Qué es**: Reintentar operaciones fallidas automáticamente.

**Cuándo usar**:
- Fallos transitorios de red
- Problemas temporales de BD (locks, timeouts)
- Servicios con disponibilidad intermitente

**Implementación**:
```python
for attempt in range(1, retries + 1):
    try:
        # Intentar operación
        return success()
    except Error:
        time.sleep(delay)  # Backoff
# Todos los intentos fallaron
return failure()
```

**Estrategias de backoff**:
- **Fixed delay**: Esperar tiempo fijo (ej: 0.3s)
- **Exponential backoff**: 1s → 2s → 4s → 8s
- **Jitter**: Agregar aleatoriedad para evitar thundering herd

---

### 6. **Saga Pattern (Transacciones Distribuidas)**
**Ubicación**: [services/reservations/app.py](services/reservations/app.py#L93)

**Problema**: No hay ACID en sistemas distribuidos (no hay un solo coordinador de transacciones).

**Solución Saga**: Secuencia de transacciones locales con compensaciones.

**Flujo en nuestro sistema**:
```
1. Reservar inventario → OK
2. Procesar pago → FALLO
3. Compensar: Liberar inventario (rollback manual)
```

**Tipos de Saga**:
- **Orquestación** (usado aquí): Un servicio coordina todo
- **Coreografía**: Cada servicio sabe qué hacer (eventos)

**Código crítico**:
```python
# Paso 1: Reservar
inventory_response = requests.post(f"{INVENTORY_URL}/reserve")

# Paso 2: Pagar (si falla, compensar)
try:
    payment_response = requests.post(f"{PAYMENTS_URL}/pay")
except:
    _release_inventory(payload)  # COMPENSATING TRANSACTION
    return error()
```

---

### 7. **Compensating Transactions**
**Ubicación**: [services/reservations/app.py](services/reservations/app.py#L180)

**Qué es**: "Deshacer" una operación exitosa cuando falla un paso posterior.

**Ejemplo**:
```python
def _release_inventory(payload):
    """Devuelve asientos al inventario (rollback)"""
    requests.post(f"{INVENTORY_URL}/release", json=payload)
```

**Escenarios de uso**:
- Pago fallido → Liberar inventario
- BD no disponible → Liberar inventario
- Timeout en pago → Liberar inventario (por seguridad)

**Limitación importante**: 
No siempre es posible compensar perfectamente (ej: si ya se cobró, necesitas hacer refund).

---

### 8. **Graceful Degradation (Degradación Graciosa)**
**Ubicación**: [services/reservations/app.py](services/reservations/app.py#L170)

**Qué es**: El sistema sigue funcionando parcialmente aunque falle un componente no crítico.

**Ejemplo**:
```python
# Notificar usuario (NO CRÍTICO)
notified, error = notify_user(payload)

# Si falla, la reserva SIGUE SIENDO VÁLIDA
return success({
    "message": "Reserva confirmada",
    "notification": {"sent": notified}  # Informamos, pero no bloqueamos
})
```

**Clasificación de servicios**:
- **Críticos**: Inventory, Payments, BD → Si fallan, cancelar reserva
- **No críticos**: Notifications → Si falla, continuar igual

---

## 🧪 CHAOS ENGINEERING

### Qué es Chaos Engineering
Inyectar fallos controlados para probar la resiliencia del sistema.

### Fallos Simulados en este Proyecto

#### 1. **Servicio Caído (Crash)**
```python
# inventory/app.py
if CHAOS_FLAGS["crash"]:
    return error("Servicio caído", 503)
```

#### 2. **Latencia Alta (Slow Service)**
```python
# payments/app.py
if CHAOS_FLAGS["latency_seconds"] > 0:
    time.sleep(CHAOS_FLAGS["latency_seconds"])
```

#### 3. **Base de Datos Intermitente (Flapping)**
```python
# reservations/app.py
if CHAOS_FLAGS["db_flapping"] and random.random() < 0.5:
    raise sqlite3.OperationalError("Conexión intermitente")
```

#### 4. **Servicio Completamente Inactivo**
```python
# notifications/app.py
if CHAOS_FLAGS["down"]:
    return error("Servicio inactivo", 503)
```

---

## 🔢 CÓDIGOS HTTP IMPORTANTES

| Código | Significado | Cuándo usarlo |
|--------|-------------|---------------|
| **200** | OK | Operación exitosa |
| **409** | Conflict | No hay inventario disponible |
| **429** | Too Many Requests | Gateway saturado (rate limiting) |
| **502** | Bad Gateway | Servicio downstream respondió con error |
| **503** | Service Unavailable | Servicio no disponible (caído, timeout) |
| **504** | Gateway Timeout | El servicio tardó demasiado en responder |

---

## 🧵 CONCURRENCIA Y PARALELISMO

### ThreadPoolExecutor
**Ubicación**: [scripts/load_gateway.py](scripts/load_gateway.py)

**Qué es**: Ejecutar múltiples tareas en paralelo usando threads.

```python
with ThreadPoolExecutor(max_workers=10) as executor:
    # Envía 10 peticiones simultáneamente
    futures = [executor.submit(make_request, i) for i in range(10)]
    for future in as_completed(futures):
        result = future.result()
```

**Diferencia Thread vs Proceso**:
- **Thread**: Comparte memoria, ideal para I/O (network, disk)
- **Process**: Memoria separada, ideal para CPU-intensive

---

## 🐳 DOCKER Y ORQUESTACIÓN

### Docker Compose
**Ubicación**: [docker-compose.yml](docker-compose.yml)

**Conceptos clave**:

#### 1. **Servicios**
Cada contenedor es un servicio independiente.

#### 2. **Networking**
Docker crea una red interna donde los servicios se comunican por nombre:
```yaml
environment:
  - INVENTORY_URL=http://inventory:5002  # "inventory" es el nombre del servicio
```

#### 3. **Volúmenes (Persistencia)**
```yaml
volumes:
  - reservations-data:/data  # Los datos sobreviven al reinicio
```

#### 4. **Ports (Exposición)**
```yaml
ports:
  - "5000:5000"  # host:container
```

#### 5. **Depends_on**
```yaml
depends_on:
  - inventory  # Espera que inventory inicie primero
```

**IMPORTANTE**: `depends_on` solo espera que el contenedor inicie, NO que esté "ready" para aceptar conexiones.

---

## 📊 PRUEBAS Y VALIDACIÓN

### 1. Load Testing (Prueba de Carga)
**Script**: [scripts/load_gateway.py](scripts/load_gateway.py)

**Objetivo**: Verificar comportamiento bajo alta concurrencia.

**Métricas importantes**:
- Throughput (peticiones/segundo)
- Tasa de éxito/error
- Códigos HTTP recibidos (200, 429, 503, etc.)

### 2. Race Condition Test
**Script**: [scripts/race_condition.py](scripts/race_condition.py)

**Objetivo**: Verificar que el lock funciona correctamente.

**Escenario**:
1. Inventario = 1 asiento
2. 2 peticiones simultáneas
3. Resultado esperado: 1 exitosa (200), 1 rechazada (409)

---

## 🎯 PREGUNTAS CLAVE PARA TU EXAMEN

### Conceptuales
1. **¿Qué es una race condition? ¿Cómo se previene?**
   - Dos threads accediendo a datos compartidos sin sincronización
   - Prevención: Locks, operaciones atómicas, semáforos

2. **¿Por qué son importantes los timeouts?**
   - Evitan bloqueos indefinidos
   - Permiten liberar recursos
   - Fundamental para fail-fast

3. **¿Qué es una transacción distribuida?**
   - Operación que involucra múltiples servicios/BDs
   - No hay ACID como en BDs monolíticas
   - Se usa Saga Pattern

4. **¿Diferencia entre Orquestación y Coreografía?**
   - Orquestación: Un servicio coordina (usado aquí)
   - Coreografía: Cada servicio reacciona a eventos

5. **¿Qué es Chaos Engineering?**
   - Inyectar fallos para probar resiliencia
   - Ejemplos: latencia, crashes, network partitions

### Técnicas
1. **¿Cómo manejas un servicio lento?**
   - Timeouts
   - Circuit breaker (no implementado aquí)
   - Retry con backoff

2. **¿Cómo garantizas consistencia sin transacciones ACID?**
   - Saga Pattern
   - Compensating transactions
   - Eventual consistency

3. **¿Cuándo usar locks?**
   - Operaciones read-modify-write
   - Acceso a recursos compartidos
   - Prevenir race conditions

4. **¿Qué hacer cuando falla un paso en una transacción distribuida?**
   - Compensating transactions (rollback manual)
   - Registrar en logs para reconciliación
   - Notificar al usuario

---

## 💡 MEJORES PRÁCTICAS (Best Practices)

1. **SIEMPRE usa timeouts** en operaciones de red
2. **Clasifica servicios** en críticos vs no críticos
3. **Implementa reintentos** para fallos transitorios
4. **Protege secciones críticas** con locks
5. **Loguea errores** para debugging y auditoría
6. **Fail fast** cuando no puedas recuperarte
7. **Degrada gracefully** cuando sea posible
8. **Prueba con Chaos Engineering** antes de producción

---

## 🔗 FLUJO COMPLETO DE UNA RESERVA

```
1. Cliente → Gateway (5000)
   ↓ (semáforo, timeout 5s)
   
2. Gateway → Reservations (5001)
   ↓
   
3. Reservations → Inventory (5002)
   └─ Reservar asientos (timeout 2s)
   └─ Si falla → Abortar
   
4. Reservations → Payments (5003)
   └─ Procesar pago (timeout 3s)
   └─ Si falla → Liberar inventario
   
5. Reservations → BD Local
   └─ Guardar reserva (3 reintentos)
   └─ Si falla → Liberar inventario
   
6. Reservations → Notifications (5004)
   └─ Enviar email (timeout 2s)
   └─ Si falla → Continuar igual (no crítico)
   
7. Reservations → Gateway → Cliente
   └─ Respuesta 200 OK
```

---

## 📖 TÉRMINOS CLAVE

- **Backpressure**: Mecanismo para frenar peticiones cuando el sistema está sobrecargado
- **Circuit Breaker**: Patrón que detiene peticiones a un servicio que está fallando
- **Eventual Consistency**: Los datos eventualmente serán consistentes (no inmediato)
- **Idempotencia**: Ejecutar una operación N veces = ejecutarla 1 vez
- **Distributed Transaction**: Transacción que abarca múltiples servicios/BDs
- **Compensating Transaction**: Operación que "deshace" una transacción previa
- **Saga Pattern**: Patrón para manejar transacciones distribuidas
- **Chaos Engineering**: Práctica de inyectar fallos para probar resiliencia

---

## ✅ CHECKLIST DE ESTUDIO

- [ ] Entiendes qué es una race condition y cómo prevenirla
- [ ] Puedes explicar el Saga Pattern
- [ ] Sabes por qué son críticos los timeouts
- [ ] Entiendes la diferencia entre servicios críticos y no críticos
- [ ] Puedes implementar retry logic con backoff
- [ ] Conoces los códigos HTTP principales (200, 409, 429, 503, 504)
- [ ] Sabes qué es una compensating transaction
- [ ] Entiendes cómo funcionan los locks/semáforos
- [ ] Puedes explicar el flujo completo de una reserva
- [ ] Conoces los beneficios y desventajas de microservicios

---

## 🚀 ¡Buena suerte en tu examen!

Recuerda: La clave no es memorizar código, sino **entender los conceptos y patrones** que resuelven problemas en sistemas distribuidos.
