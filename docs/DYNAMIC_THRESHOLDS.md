# Configuración Dinámica de Thresholds de Alertas

Este documento explica cómo funciona el sistema de configuración dinámica de thresholds de alertas, que permite modificar los umbrales sin reiniciar el servicio.

## Descripción General

El sistema de monitoreo permite configurar dinámicamente los umbrales (thresholds) de las alertas:
- **Data Drift**: Umbral de desviación de datos
- **Latencia**: Umbral máximo de latencia en milisegundos
- **Tasa de Errores**: Tasa máxima de errores permitida
- **Confidence Drop**: Umbral de caída de confianza

Los cambios se aplican **automáticamente sin reiniciar el servicio**, con un tiempo máximo de propagación de 60 segundos debido al sistema de caché.

## Características Principales

### 1. Sin Reinicio del Servicio
- Los cambios se aplican en caliente (hot reload)
- Máximo 60 segundos para que los cambios surtan efecto
- No hay downtime del servicio

### 2. Sistema de Caché Inteligente
- Caché de 60 segundos (TTL)
- Reduce carga en la base de datos
- Recarga automática al expirar

### 3. Configuración por Servicio
- Puedes tener thresholds diferentes para cada servicio (search, sentiment)
- Los overrides específicos tienen prioridad sobre los valores globales

### 4. Historial de Cambios
- Cada cambio se registra con timestamp
- Se guarda quién realizó el cambio
- Se puede agregar una descripción del cambio

## API Endpoints

### 1. Obtener Configuración Actual

**Endpoint:** `GET /api/v1/alerts/config/thresholds`

**Parámetros opcionales:**
- `service_name`: Nombre del servicio (search, sentiment) para obtener overrides específicos

**Ejemplo de Request:**
```bash
curl http://localhost:8003/api/v1/alerts/config/thresholds
```

**Ejemplo de Response:**
```json
{
  "drift_threshold": 0.3,
  "confidence_drop_threshold": 0.1,
  "latency_threshold_ms": 2000,
  "error_rate_threshold": 0.05,
  "service_overrides": null,
  "updated_at": "2025-11-06T10:30:45.123456",
  "updated_by": "system_init"
}
```

**Con overrides por servicio:**
```bash
curl http://localhost:8003/api/v1/alerts/config/thresholds?service_name=search
```

```json
{
  "drift_threshold": 0.25,
  "confidence_drop_threshold": 0.1,
  "latency_threshold_ms": 1500,
  "error_rate_threshold": 0.05,
  "service_overrides": {
    "search": {
      "drift_threshold": 0.25,
      "latency_threshold_ms": 1500
    }
  },
  "updated_at": "2025-11-06T11:00:00.000000",
  "updated_by": "admin_user"
}
```

### 2. Actualizar Configuración

**Endpoint:** `PUT /api/v1/alerts/config/thresholds`

**Request Body:** JSON con los valores a actualizar (todos opcionales)

**Ejemplo 1: Actualizar threshold de drift**
```bash
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "drift_threshold": 0.25,
    "description": "Reducir threshold para ser más sensible a drift",
    "updated_by": "admin_user"
  }'
```

**Ejemplo 2: Actualizar latencia y error rate**
```bash
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "latency_threshold_ms": 1500,
    "error_rate_threshold": 0.03,
    "description": "Reducir tolerancia a latencia y errores",
    "updated_by": "admin_user"
  }'
```

**Ejemplo 3: Configurar overrides por servicio**
```bash
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "service_overrides": {
      "search": {
        "drift_threshold": 0.25,
        "latency_threshold_ms": 1500
      },
      "sentiment": {
        "drift_threshold": 0.35,
        "latency_threshold_ms": 2500
      }
    },
    "description": "Configuración específica por servicio",
    "updated_by": "admin_user"
  }'
```

**Response:**
```json
{
  "drift_threshold": 0.25,
  "confidence_drop_threshold": 0.1,
  "latency_threshold_ms": 1500,
  "error_rate_threshold": 0.03,
  "service_overrides": null,
  "updated_at": "2025-11-06T12:00:00.000000",
  "updated_by": "admin_user"
}
```

### 3. Invalidar Caché Manualmente

**Endpoint:** `POST /api/v1/alerts/config/thresholds/invalidate-cache`

Este endpoint fuerza la recarga inmediata de la configuración desde la base de datos, en lugar de esperar los 60 segundos del TTL del caché.

**Ejemplo:**
```bash
curl -X POST http://localhost:8003/api/v1/alerts/config/thresholds/invalidate-cache
```

**Response:**
```json
{
  "status": "success",
  "message": "Threshold cache invalidated. New values will be loaded on next access."
}
```

## Uso con Python

### Ejemplo: Actualizar thresholds desde script

```python
import requests
import json

# URL del servicio de monitoreo
BASE_URL = "http://localhost:8003/api/v1"

# Actualizar threshold de drift para generar más alertas
response = requests.put(
    f"{BASE_URL}/alerts/config/thresholds",
    json={
        "drift_threshold": 0.2,
        "description": "Threshold más bajo para testing",
        "updated_by": "test_script"
    }
)

if response.status_code == 200:
    config = response.json()
    print(f"✅ Threshold actualizado: {config['drift_threshold']}")
    print(f"   Actualizado por: {config['updated_by']}")
    print(f"   Fecha: {config['updated_at']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

# Invalidar caché para aplicar cambios inmediatamente
invalidate = requests.post(f"{BASE_URL}/alerts/config/thresholds/invalidate-cache")
if invalidate.status_code == 200:
    print("✅ Caché invalidado - cambios aplicados inmediatamente")
```

### Ejemplo: Obtener configuración actual

```python
import requests

BASE_URL = "http://localhost:8003/api/v1"

# Obtener configuración global
response = requests.get(f"{BASE_URL}/alerts/config/thresholds")
config = response.json()

print(f"Configuración actual:")
print(f"  • Drift threshold: {config['drift_threshold']}")
print(f"  • Latency threshold: {config['latency_threshold_ms']} ms")
print(f"  • Error rate threshold: {config['error_rate_threshold']}")
print(f"  • Última actualización: {config['updated_at']}")

# Obtener configuración específica para search
response = requests.get(
    f"{BASE_URL}/alerts/config/thresholds",
    params={"service_name": "search"}
)
search_config = response.json()
print(f"\nConfiguración para search service:")
print(f"  • Drift threshold: {search_config['drift_threshold']}")
print(f"  • Latency threshold: {search_config['latency_threshold_ms']} ms")
```

## Flujo de Trabajo Típico

### Escenario 1: Ajustar Sensibilidad para Detectar Más Drift

1. **Obtener configuración actual:**
```bash
curl http://localhost:8003/api/v1/alerts/config/thresholds
```

2. **Reducir el threshold de drift:**
```bash
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "drift_threshold": 0.2,
    "description": "Incrementar sensibilidad para detectar cambios más sutiles",
    "updated_by": "ml_engineer"
  }'
```

3. **Forzar recarga inmediata:**
```bash
curl -X POST http://localhost:8003/api/v1/alerts/config/thresholds/invalidate-cache
```

4. **Verificar que se están generando alertas**

5. **Cuando tengas suficientes datos, ajustar el threshold:**
```bash
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "drift_threshold": 0.28,
    "description": "Ajuste basado en observaciones",
    "updated_by": "ml_engineer"
  }'
```

### Escenario 2: Preparar Cambio de Modelo

Cuando planeas cambiar un modelo, puedes reducir temporalmente los thresholds para detectar problemas más rápido:

```bash
# Antes del cambio - incrementar sensibilidad
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "drift_threshold": 0.15,
    "latency_threshold_ms": 1000,
    "error_rate_threshold": 0.02,
    "description": "Pre-deployment: alta sensibilidad",
    "updated_by": "deployment_script"
  }'

# Invalidar caché
curl -X POST http://localhost:8003/api/v1/alerts/config/thresholds/invalidate-cache

# ... realizar cambio de modelo ...

# Después de validar - volver a valores normales
curl -X PUT http://localhost:8003/api/v1/alerts/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "drift_threshold": 0.3,
    "latency_threshold_ms": 2000,
    "error_rate_threshold": 0.05,
    "description": "Post-deployment: valores normales",
    "updated_by": "deployment_script"
  }'
```

## Validación de Valores

Los valores están validados automáticamente:

- `drift_threshold`: 0.0 - 1.0 (flotante)
- `confidence_drop_threshold`: 0.0 - 1.0 (flotante)
- `latency_threshold_ms`: >= 0 (entero)
- `error_rate_threshold`: 0.0 - 1.0 (flotante)

Si intentas usar valores fuera de rango, recibirás un error 422 (Unprocessable Entity).

## Arquitectura del Sistema

```
┌─────────────────┐
│  API Request    │
│  PUT /thresholds│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ ThresholdConfigService      │
│ • update_thresholds()       │
│ • Validar valores           │
│ • Guardar en BD             │
│ • Invalidar caché           │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Base de Datos               │
│ alert_threshold_config      │
│ • Guardar nueva config      │
│ • Timestamp de actualización│
└─────────────────────────────┘

┌─────────────────────────────┐
│ Detección de Drift          │
│ evidently_service           │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ AlertService                │
│ • check_drift_alerts()      │
│ • Obtener thresholds        │
│   desde caché/BD            │
│ • Comparar con métricas     │
│ • Crear alerta si excede    │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ RabbitMQ Publisher          │
│ • Publicar evento de alerta │
└─────────────────────────────┘
```

## Sistema de Caché

El sistema usa un caché simple con TTL (Time To Live):

- **TTL**: 60 segundos
- **Invalidación automática**: Al actualizar configuración
- **Invalidación manual**: Endpoint `/invalidate-cache`
- **Fallback**: Si falla la BD, usa valores de `config.py`

### Tiempo de Propagación

Después de actualizar un threshold:

| Escenario | Tiempo de Propagación |
|-----------|----------------------|
| Con invalidación manual | ~0 segundos |
| Sin invalidación manual | 0-60 segundos (depende del tiempo restante en caché) |

## Mejores Prácticas

### 1. Documentar Cambios
Siempre incluye una `description` al actualizar thresholds:
```json
{
  "drift_threshold": 0.25,
  "description": "Reducir threshold por cambio en pipeline de datos",
  "updated_by": "nombre_usuario"
}
```

### 2. Cambios Graduales
Haz cambios incrementales en lugar de saltos grandes:
```bash
# ❌ Mal: Cambio brusco
"drift_threshold": 0.5 → 0.1

# ✅ Bien: Cambios graduales
"drift_threshold": 0.5 → 0.4 → 0.3 → 0.25
```

### 3. Invalidar Caché en Cambios Críticos
Para cambios importantes, invalida el caché manualmente:
```bash
# 1. Actualizar threshold
curl -X PUT .../thresholds -d '{...}'

# 2. Invalidar caché
curl -X POST .../invalidate-cache
```

### 4. Monitorear Alertas
Después de cambiar thresholds, monitorea las alertas generadas:
```bash
# Ver alertas recientes
curl http://localhost:8003/api/v1/alerts?limit=10
```

## Troubleshooting

### Las alertas no se generan después de reducir el threshold

**Posibles causas:**
1. Caché aún no expiró (espera hasta 60 segundos)
2. No hay drift real en los datos

**Solución:**
```bash
# 1. Invalidar caché
curl -X POST http://localhost:8003/api/v1/alerts/config/thresholds/invalidate-cache

# 2. Verificar configuración actual
curl http://localhost:8003/api/v1/alerts/config/thresholds

# 3. Ver logs del servicio para confirmar que se está usando la nueva configuración
```

### Los cambios no se persisten al reiniciar

Si los cambios se pierden al reiniciar el servicio:

1. Verifica que la base de datos esté configurada correctamente
2. Revisa los logs de inicialización:
   - Debe aparecer: `threshold_config_initialized`
   - NO debe aparecer: `no_active_threshold_config_found`

### Valores vuelven a los defaults

Si los valores vuelven a los defaults de `config.py`:

1. Revisa que la configuración en BD esté marcada como `is_active=True`
2. Verifica la conexión a la base de datos
3. Revisa los logs para ver si hay errores al cargar desde BD

## Integración con CI/CD

Puedes automatizar la configuración de thresholds en tu pipeline:

```yaml
# .github/workflows/deploy-ml-model.yml
steps:
  - name: Deploy Model
    run: ./deploy_model.sh

  - name: Set Sensitive Thresholds
    run: |
      curl -X PUT http://monitoring-service/api/v1/alerts/config/thresholds \
        -H "Content-Type: application/json" \
        -d '{
          "drift_threshold": 0.15,
          "latency_threshold_ms": 1000,
          "description": "Post-deployment monitoring",
          "updated_by": "ci-cd-pipeline"
        }'

      # Invalidar caché
      curl -X POST http://monitoring-service/api/v1/alerts/config/thresholds/invalidate-cache

  - name: Monitor for 1 hour
    run: sleep 3600

  - name: Restore Normal Thresholds
    run: |
      curl -X PUT http://monitoring-service/api/v1/alerts/config/thresholds \
        -H "Content-Type: application/json" \
        -d '{
          "drift_threshold": 0.3,
          "latency_threshold_ms": 2000,
          "description": "Back to normal",
          "updated_by": "ci-cd-pipeline"
        }'
```

## Referencias

- **Código fuente**:
  - `src/models/database.py:198-220` - Modelo de BD
  - `src/services/threshold_config_service.py` - Servicio de configuración
  - `src/services/alert_service.py:65-105` - Uso en alertas
  - `src/api/routes/alerts.py:184-287` - Endpoints API

- **Configuración estática**: `src/core/config.py:46-50`
