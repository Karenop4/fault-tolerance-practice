# Sistema de Reservas de Entradas (Práctica de Tolerancia a Fallos)

Este repositorio contiene una arquitectura simplificada de venta de tickets con varios servicios y *chaos monkeys* para simular fallos. La idea es demostrar que, ante fallos controlados, el sistema responde con mensajes claros y no colapsa.

## 🧱 Arquitectura

- **API Gateway**: Punto de entrada para clientes y UI.
- **Servicio de Reservas (Core)**: Orquesta inventario, pagos, notificaciones y persistencia.
- **Servicio de Inventario**: Verifica y descuenta asientos.
- **Servicio de Pagos (Simulado)**: Procesa pagos con latencia configurable.
- **Servicio de Notificaciones**: Envío de correo (no crítico).
- **Base de Datos**: SQLite para persistencia de reservas.

## ✅ Requisitos

- Docker y Docker Compose
- Python 3.11+ (solo si quieres ejecutar scripts localmente)

## ▶️ Ejecución

```bash
docker compose up --build
```

Abre la UI en: [http://localhost:5000](http://localhost:5000)

## 🧪 Chaos Monkeys (6 fallos)

Cada script en `scripts/` activa o desactiva una falla. Úsalos mientras haces una reserva desde la UI o con `curl`.

> Todos los servicios devuelven **errores controlados** (JSON legible) y nunca terminan en una excepción sin manejar.

### 1) "El Inventario Fantasma" (Crash)

Simula que el inventario está caído.

```bash
./scripts/crash_inventory.sh true
./scripts/crash_inventory.sh false
```

**Resultado esperado:** el API Gateway devuelve un error claro indicando que el inventario está inactivo.

### 2) "La Pasarela Lenta" (Latencia)

Simula 20s de latencia en pagos.

```bash
./scripts/slow_payments.sh 20
./scripts/slow_payments.sh 0
```

**Resultado esperado:** el Servicio de Reservas cancela el pago por timeout y libera el inventario.

### 3) "El Diluvio de Peticiones" (Sobrecarga)

Envia muchas solicitudes para saturar el API Gateway y disparar el límite de solicitudes en vuelo.

```bash
python scripts/load_gateway.py --requests 50 --workers 10
```

**Resultado esperado:** se reciben respuestas 429 con mensaje de saturación, pero el gateway sigue funcionando.

### 4) "Base de Datos Intermitente" (Flapping)

```bash
./scripts/db_flap.sh true
./scripts/db_flap.sh false
```

**Resultado esperado:** el Servicio de Reservas reintenta y responde con error controlado si no puede persistir.

### 5) "El Correo Perdido" (Fallo no crítico)

```bash
./scripts/notifications_down.sh true
./scripts/notifications_down.sh false
```

**Resultado esperado:** la reserva es exitosa, pero la respuesta indica que la notificación falló.

### 6) "Condición de Carrera" (Consistencia)

Dispara dos compras simultáneas por el último asiento disponible:

```bash
python scripts/race_condition.py
```

**Resultado esperado:** una compra es aceptada y la otra recibe un error de "No hay asientos disponibles".

## 🔌 Endpoints principales

- `GET /` - UI de prueba
- `POST /api/reserve` - Entrada al API Gateway
- `POST /reserve` - Endpoint interno del Servicio de Reservas
- `POST /reserve` - Inventario (reserva)
- `POST /release` - Inventario (libera asientos)
- `POST /pay` - Pagos
- `POST /send` - Notificaciones

## 🗂️ Estructura

```
services/
  gateway/
  reservations/
  inventory/
  payments/
  notifications/
scripts/
```

## 📝 Nota sobre diseño

Las protecciones incluyen:

- **Timeouts y mensajes controlados** entre servicios.
- **Límite de solicitudes concurrentes** en el API Gateway.
- **Reintentos** y manejo de errores en la persistencia.
- **Liberación del inventario** si falla el pago.
- **Manejo de fallos no críticos** (notificaciones).
- **Bloqueos (locks)** en el inventario para evitar condiciones de carrera.
