# ⚙️ Guía de Configuración - ML Monitoring Service

Esta guía explica **todas las opciones configurables** del servicio de monitoreo.

---

## 📋 Tabla de Contenidos

1. [Configuración Básica](#configuración-básica)
2. [Reportes Automáticos](#reportes-automáticos)
3. [Thresholds de Alertas](#thresholds-de-alertas)
4. [Integraciones Externas](#integraciones-externas)
5. [Retención de Datos](#retención-de-datos)
6. [Optimización](#optimización)
7. [Casos de Uso](#casos-de-uso)

---

## 🚀 Configuración Básica

### 1. Copiar el archivo de ejemplo

```bash
cd monitoring-service/ecommerce-ml-monitoring
cp .env.example .env
```

### 2. Configuración Mínima (Para Empezar)

```bash
# Solo necesitas cambiar esto para empezar
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./data/monitoring.db

# URLs de tus servicios
SEARCH_SERVICE_URL=http://localhost:8000
SENTIMENT_SERVICE_URL=http://localhost:8002
```

**¡Con esto ya funciona!** El resto son opcionales.

---

## 📊 Reportes Automáticos

### ¿Cómo Funciona?

**Actualmente:** Los reportes se generan **manualmente** cuando llamas al API.

**Con Auto-Reports:** El sistema genera reportes **automáticamente** según un schedule.

### Configuración

```bash
# Habilitar reportes automáticos
AUTO_REPORTS_ENABLED=true

# Cada 6 horas - Reporte de Drift
DRIFT_REPORT_CRON=0 */6 * * *
DRIFT_REPORT_ENABLED=true

# Cada hora - Reporte de Performance
PERFORMANCE_REPORT_CRON=0 */1 * * *
PERFORMANCE_REPORT_ENABLED=true

# Diario a las 9 AM - Reporte completo
DAILY_REPORT_CRON=0 9 * * *
DAILY_REPORT_ENABLED=true

# Semanal (Lunes 10 AM) - Resumen semanal
WEEKLY_REPORT_CRON=0 10 * * 1
WEEKLY_REPORT_ENABLED=true
```

### Formato Cron Explicado

```
┌───────────── minuto (0 - 59)
│ ┌───────────── hora (0 - 23)
│ │ ┌───────────── día del mes (1 - 31)
│ │ │ ┌───────────── mes (1 - 12)
│ │ │ │ ┌───────────── día de la semana (0 - 6) (0=Domingo)
│ │ │ │ │
* * * * *
```

**Ejemplos comunes:**
```bash
0 */1 * * *    # Cada hora
0 */6 * * *    # Cada 6 horas
0 9 * * *      # Diario a las 9 AM
0 9 * * 1      # Cada lunes a las 9 AM
*/30 * * * *   # Cada 30 minutos
0 */12 * * *   # Cada 12 horas
```

### Implementación del Scheduler

**Nota:** Para que los reportes automáticos funcionen, necesitas implementar un scheduler. Opciones:

1. **APScheduler** (Python) - Ya está en requirements.txt
2. **Cron del sistema** (Linux)
3. **Celery** (Para producción)

---

## 🚨 Thresholds de Alertas

### Data Drift

```bash
# Alerta Warning si >30% de features tienen drift
DRIFT_THRESHOLD=0.3

# Alerta Critical si >50% de features tienen drift
DRIFT_CRITICAL_THRESHOLD=0.5
```

**¿Qué significa?**
- El modelo detecta cambios en la distribución de datos
- Si 30% de las características cambian → Warning
- Si 50% de las características cambian → Critical (¡reentrenar modelo!)

### Performance

```bash
# Latencia
LATENCY_THRESHOLD_MS=2000        # Warning si p95 > 2 segundos
LATENCY_CRITICAL_MS=5000         # Critical si p95 > 5 segundos

# Error Rate
ERROR_RATE_THRESHOLD=0.05        # Warning si > 5% de errores
ERROR_RATE_CRITICAL=0.15         # Critical si > 15% de errores
```

### Sentiment Service

```bash
# Alerta si la confianza promedio cae 10%
CONFIDENCE_DROP_THRESHOLD=0.1

# Alerta si muchas predicciones tienen confianza < 60%
LOW_CONFIDENCE_THRESHOLD=0.6
```

### Search Service

```bash
# Alerta si búsquedas retornan 0 resultados frecuentemente
MIN_RESULTS_THRESHOLD=0

# Alerta si el score de relevancia promedio cae
RELEVANCE_SCORE_THRESHOLD=0.5
```

### Configuración de Alertas

```bash
# Evitar spam de alertas
ALERT_COOLDOWN_MINUTES=30        # Esperar 30min antes de re-alertar
MAX_ALERTS_PER_HOUR=10           # Máximo 10 alertas por hora

# Auto-resolver
AUTO_RESOLVE_ALERTS=true         # Resolver automáticamente cuando se normalice
AUTO_RESOLVE_AFTER_HOURS=24      # Resolver después de 24h si no hay update
```

---

## 🔗 Integraciones Externas

### Slack Alerts

```bash
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/XXX
SLACK_CHANNEL=#ml-alerts
SLACK_NOTIFY_DRIFT=true
SLACK_NOTIFY_PERFORMANCE=true
SLACK_NOTIFY_ERRORS_ONLY=false   # false = notificar todo, true = solo errores
```

**Cómo obtener el webhook:**
1. Ve a https://api.slack.com/apps
2. Crea una app nueva
3. Activa "Incoming Webhooks"
4. Copia la URL

### Email Alerts

```bash
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_FROM=monitoring@tuempresa.com
EMAIL_TO=equipo@tuempresa.com
EMAIL_DAILY_SUMMARY=true
```

### Prometheus (Métricas)

```bash
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

Accede a métricas en: `http://localhost:9090/metrics`

### InfluxDB (Time-series)

```bash
INFLUXDB_ENABLED=true
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=tu-token
INFLUXDB_ORG=ecommerce
INFLUXDB_BUCKET=ml_metrics
```

### S3/MinIO (Storage)

```bash
S3_ENABLED=true
S3_ENDPOINT=http://localhost:9000  # MinIO local
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=ml-reports
S3_AUTO_UPLOAD_REPORTS=true        # Auto-subir reportes HTML
```

---

## 🗄️ Retención de Datos

### Limpieza Automática

```bash
# Habilitar limpieza automática
AUTO_CLEANUP_ENABLED=true
CLEANUP_SCHEDULE_CRON=0 2 * * *   # Cada día a las 2 AM

# Logs de predicciones
PREDICTION_LOG_RETENTION_DAYS=30  # Mantener 30 días

# Reportes
REPORT_RETENTION_DAYS=90          # Mantener 90 días
KEEP_CRITICAL_REPORTS=true        # Nunca borrar reportes con alertas críticas
```

### Reference Data

```bash
# Máximo de versiones anteriores a mantener
REFERENCE_DATA_MAX_VERSIONS=5

# Auto-actualizar reference data semanalmente
AUTO_UPDATE_REFERENCE=true
REFERENCE_UPDATE_CRON=0 3 * * 0   # Domingos a las 3 AM
```

---

## ⚡ Optimización

### Batch Processing

```bash
# Procesar predicciones en lotes
BATCH_SIZE=1000

# Limitar embeddings para análisis de drift (ahorra RAM)
MAX_EMBEDDING_SAMPLES=10000
```

### Report Generation

```bash
# Máximo de muestras por reporte
REPORT_MAX_SAMPLES=50000

# Timeout de generación
REPORT_TIMEOUT_SECONDS=300        # 5 minutos

# Generar reportes en paralelo (usar con cuidado)
PARALLEL_REPORT_GENERATION=false
```

### Database

```bash
# Pool de conexiones
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Debug SQL (solo desarrollo)
DB_ECHO=false
```

### Cache

```bash
# Cachear resultados de reportes
ENABLE_CACHE=true
CACHE_TTL_SECONDS=3600            # 1 hora
```

### Sampling (Alto Volumen)

```bash
# Si tienes >10k predicciones/día, considera sampling
SAMPLING_ENABLED=true
SAMPLING_RATE=0.1                 # Loguear 10% de predicciones
SAMPLING_ENSURE_DIVERSITY=true    # Asegurar muestras diversas
```

---

## 📖 Casos de Uso

### Caso 1: Desarrollo (Default)

```bash
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./data/monitoring.db
AUTO_REPORTS_ENABLED=false        # Manual reports
SLACK_ENABLED=false
```

### Caso 2: Producción Pequeña (<1000 req/día)

```bash
APP_ENV=production
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./data/monitoring.db
AUTO_REPORTS_ENABLED=true
DRIFT_REPORT_CRON=0 */6 * * *     # Cada 6 horas
PERFORMANCE_REPORT_CRON=0 */1 * * *  # Cada hora
SLACK_ENABLED=true
PREDICTION_LOG_RETENTION_DAYS=30
```

### Caso 3: Producción Grande (>10k req/día)

```bash
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ml_monitoring
AUTO_REPORTS_ENABLED=true
SAMPLING_ENABLED=true
SAMPLING_RATE=0.1                 # Sample 10%
S3_ENABLED=true
S3_AUTO_UPLOAD_REPORTS=true
INFLUXDB_ENABLED=true
SLACK_ENABLED=true
EMAIL_ENABLED=true
DB_POOL_SIZE=20
PARALLEL_REPORT_GENERATION=true
```

### Caso 4: Alta Seguridad / Privacidad

```bash
# No loguear datos sensibles
MONITORING_LOG_TEXT=false         # No loguear texto completo
MONITORING_ANONYMIZE_TEXT=true    # Hashear textos
MAX_TEXT_LENGTH=50                # Solo primeros 50 chars
SLACK_NOTIFY_ERRORS_ONLY=true     # No enviar datos a Slack
KEEP_CRITICAL_REPORTS=false       # No mantener reportes indefinidamente
```

---

## 🔍 Verificar Configuración

```bash
# Ver configuración activa
curl http://localhost:8003/api/v1/info | jq

# Ver features habilitadas
curl http://localhost:8003/api/v1/info | jq '.features'
```

---

## 💡 Tips

### ¿Qué configurar primero?

1. **URLs de servicios** - Básico
2. **Thresholds de alertas** - Ajusta según tu SLA
3. **Slack** - Para recibir notificaciones
4. **Reportes automáticos** - Una vez estable
5. **Retención de datos** - Según tu capacidad de almacenamiento
6. **Optimización** - Solo si tienes problemas de performance

### ¿Cada cuánto ejecutar reportes?

| Volumen de Tráfico | Drift Reports | Performance Reports |
|---------------------|---------------|---------------------|
| Bajo (<100 req/día) | Diario | Cada 6 horas |
| Medio (100-1k/día) | Cada 6 horas | Cada hora |
| Alto (>1k/día) | Cada hora | Cada 30 min |

### ¿Cuándo activar sampling?

- **Activar si:** >5k predicciones/día
- **Rate recomendado:** 10-20% (0.1-0.2)
- **Beneficio:** Reduce carga en DB y reportes más rápidos

---

## 🆘 Troubleshooting

**Los reportes automáticos no se ejecutan:**
- Verifica que `AUTO_REPORTS_ENABLED=true`
- Implementa el scheduler (APScheduler)
- Revisa los logs del servicio

**Alertas de spam:**
- Aumenta `ALERT_COOLDOWN_MINUTES`
- Reduce `MAX_ALERTS_PER_HOUR`
- Ajusta thresholds

**Performance lenta:**
- Habilita `SAMPLING_ENABLED=true`
- Reduce `REPORT_MAX_SAMPLES`
- Aumenta `DB_POOL_SIZE`
- Considera PostgreSQL en lugar de SQLite

---

**Versión:** 1.0.0
**Última actualización:** 2025-10-20
