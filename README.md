# E-commerce ML Monitoring Service

Sistema de monitoreo de Machine Learning usando **Evidently AI** para rastrear drift de datos, rendimiento de modelos y calidad de datos en servicios de ML en producción.

## 📊 Servicios Monitoreados

### 1. **Search Service** (Búsqueda Semántica)
- Modelo: `paraphrase-multilingual-MiniLM-L12-v2`
- Dimensión: 384d embeddings
- Monitoreo:
  - Drift de embeddings
  - Distribución de queries
  - Performance de búsqueda
  - Scores semánticos

### 2. **Sentiment Service** (Análisis de Sentimientos)
- Modelo: `XLMRoBERTa_Multilingual_Sentiment_Analysis`
- Clases: positive, negative, neutral
- Monitoreo:
  - Drift de predicciones
  - Distribución de confianza
  - Balance de clases
  - Calidad de texto

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────┐
│   ML Monitoring Service (Evidently AI)     │
│              Puerto: 8003                    │
├─────────────────────────────────────────────┤
│  • FastAPI                                  │
│  • Evidently AI                             │
│  • SQLite/PostgreSQL                        │
│  • Prometheus (opcional)                    │
│  • Slack Alerts (opcional)                  │
└─────────────────────────────────────────────┘
         ↑                    ↑
         │                    │
    ┌────┴──────┐      ┌─────┴─────────┐
    │  Search   │      │  Sentiment    │
    │  Service  │      │   Service     │
    │  :8000    │      │   :8002       │
    └───────────┘      └───────────────┘
```

## 🚀 Instalación

### Requisitos
- Python 3.10+
- SQLite (desarrollo) o PostgreSQL (producción)

### Instalación Rápida

```bash
# 1. Clonar o navegar al directorio
cd monitoring-service/ecommerce-ml-monitoring

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env según tus necesidades

# 5. Inicializar base de datos
python -c "import asyncio; from src.storage.database import init_db; asyncio.run(init_db())"

# 6. Ejecutar servicio
python -m uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload
```

## 📝 Configuración

### Variables de Entorno Clave

```bash
# Base de datos
DATABASE_URL=sqlite+aiosqlite:///./data/monitoring.db

# URLs de servicios ML
SEARCH_SERVICE_URL=http://localhost:8000
SENTIMENT_SERVICE_URL=http://localhost:8002

# Thresholds de alertas
DRIFT_THRESHOLD=0.3
LATENCY_THRESHOLD_MS=2000
ERROR_RATE_THRESHOLD=0.05

# Slack (opcional)
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
```

## 🔧 Uso

### 1. Logging de Predicciones

Los servicios ML deben enviar logs de sus predicciones:

#### Search Service
```python
import httpx

async def log_search_prediction(query, embedding, results, latency):
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8003/api/v1/predictions/search",
            json={
                "query": query,
                "query_length": len(query),
                "embedding": embedding[:10],  # Sample
                "embedding_norm": float(np.linalg.norm(embedding)),
                "num_results": len(results),
                "top_score": float(results[0]["score"]) if results else None,
                "avg_score": float(np.mean([r["score"] for r in results])),
                "latency_ms": latency,
            }
        )
```

#### Sentiment Service
```python
async def log_sentiment_prediction(text, prediction_result, latency):
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://localhost:8003/api/v1/predictions/sentiment",
            json={
                "text": text,
                "text_length": len(text),
                "predicted_sentiment": prediction_result["predicted_sentiment"],
                "confidence": prediction_result["confidence"],
                "primary_score": prediction_result["primary_score"],
                "all_scores": prediction_result["all_scores"],
                "latency_ms": latency,
            }
        )
```

### 2. Generar Reports de Monitoreo

```bash
# Generar report para Search Service (últimas 24 horas)
curl -X POST "http://localhost:8003/api/v1/monitoring/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "search",
    "report_type": "comprehensive",
    "time_window_hours": 24,
    "include_html": true
  }'

# Generar report para Sentiment Service
curl -X POST "http://localhost:8003/api/v1/monitoring/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "sentiment",
    "report_type": "drift",
    "time_window_hours": 6
  }'
```

### 3. Ver Alertas

```bash
# Listar alertas activas
curl "http://localhost:8003/api/v1/alerts"

# Listar alertas por servicio
curl "http://localhost:8003/api/v1/alerts?service_name=search"

# Reconocer alerta
curl -X POST "http://localhost:8003/api/v1/alerts/{alert_id}/acknowledge"

# Resolver alerta
curl -X POST "http://localhost:8003/api/v1/alerts/{alert_id}/resolve"
```

### 4. Actualizar Reference Data

```bash
# Actualizar datos de referencia para Search
curl -X POST "http://localhost:8003/api/v1/monitoring/reference-data/update" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "search",
    "use_recent_data": true,
    "hours_to_sample": 168,
    "min_samples": 1000
  }'
```

## 📊 Métricas Monitoreadas

### Data Drift
- **Drift Score**: Porcentaje de features con drift significativo
- **Drift por Feature**: Score individual por cada feature
- **Threshold**: Configurable (default: 0.3)

### Performance
- **Latencia**: P50, P95, P99, Max
- **Error Rate**: Proporción de predicciones con error
- **Throughput**: Requests por minuto

### Data Quality
- **Missing Values**: Porcentaje de valores faltantes
- **Duplicates**: Cantidad de registros duplicados
- **Out of Range**: Valores fuera de rangos esperados
- **Quality Score**: Score agregado (0-1)

## 🔔 Sistema de Alertas

### Tipos de Alertas
1. **Drift Alerts**: Cuando drift_score > threshold
2. **Performance Alerts**: Latencia o error rate exceden límites
3. **Data Quality Alerts**: Calidad de datos baja
4. **Error Alerts**: Incremento en tasa de errores

### Severidades
- **Warning**: Requiere atención
- **Critical**: Requiere acción inmediata

### Canales de Notificación
- Slack (webhook)
- API endpoints para consumo
- Logs estructurados

## 📈 Reports HTML de Evidently

Los reports generados incluyen:
- Visualizaciones interactivas de drift
- Histogramas de distribuciones
- Comparación reference vs current data
- Análisis detallado por feature
- Recomendaciones automáticas

Reports guardados en: `./data/reports/`

## 🗄️ Base de Datos

### Tablas
- `search_predictions`: Logs de búsquedas
- `sentiment_predictions`: Logs de sentimientos
- `monitoring_reports`: Reports generados
- `alerts`: Alertas creadas
- `reference_data`: Metadata de datasets de referencia

### Retención de Datos
- Predicciones: 30 días (configurable)
- Reports: 90 días (configurable)

## 🔍 API Documentation

Swagger UI disponible en: `http://localhost:8003/api/v1/docs`

### Endpoints Principales

#### Predictions
- `POST /api/v1/predictions/search` - Log search prediction
- `POST /api/v1/predictions/sentiment` - Log sentiment prediction
- `GET /api/v1/predictions/search/stats` - Search stats
- `GET /api/v1/predictions/sentiment/stats` - Sentiment stats

#### Monitoring
- `POST /api/v1/monitoring/reports/generate` - Generate report
- `GET /api/v1/monitoring/reports` - List reports
- `GET /api/v1/monitoring/reports/{id}` - Get report
- `POST /api/v1/monitoring/reference-data/update` - Update reference

#### Alerts
- `GET /api/v1/alerts` - List alerts
- `GET /api/v1/alerts/{id}` - Get alert
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge
- `POST /api/v1/alerts/{id}/resolve` - Resolve

## 🧪 Testing

```bash
# Ejecutar tests
pytest tests/ -v

# Con coverage
pytest tests/ --cov=src --cov-report=html
```

## 📦 Deployment

### Docker
```bash
# Build
docker build -t ml-monitoring-service .

# Run
docker run -p 8003:8003 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite+aiosqlite:///./data/monitoring.db \
  ml-monitoring-service
```

### Producción
Para producción, considera:
- Usar PostgreSQL en lugar de SQLite
- Configurar Prometheus para métricas
- Habilitar InfluxDB para time-series
- Configurar S3/MinIO para storage de reports
- Usar APScheduler para reports automáticos

## 🔒 Consideraciones de Seguridad

1. **No loggear datos sensibles** en predicciones
2. **Limitar acceso** a la API con autenticación
3. **Usar HTTPS** en producción
4. **Rotar credenciales** regularmente
5. **Auditar acceso** a alertas y reports

## 📚 Referencias

- [Evidently AI Documentation](https://docs.evidentlyai.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [ML Monitoring Best Practices](https://ml-ops.org/content/ml-monitoring)

## 🤝 Integración con Servicios

### Search Service
Agregar en `search/ecommerce-semantic-search/api/routes.py`:

```python
from src.utils.monitoring import log_search_prediction

@router.post("/buscar")
async def search(request: SearchRequest):
    start_time = time.time()

    # ... búsqueda normal ...

    latency_ms = (time.time() - start_time) * 1000

    # Log para monitoreo
    await log_search_prediction(
        query=request.query,
        embedding=query_embedding,
        results=results,
        latency_ms=latency_ms
    )

    return results
```

### Sentiment Service
Agregar en `sentiment-service/ecommerce-sentiment-service/src/api/routes/sentiment.py`:

```python
from src.utils.monitoring import log_sentiment_prediction

@router.post("/analyze")
async def analyze(request: SentimentRequest):
    start_time = time.time()

    # ... análisis normal ...

    latency_ms = (time.time() - start_time) * 1000

    # Log para monitoreo
    await log_sentiment_prediction(
        text=request.text,
        prediction=result,
        latency_ms=latency_ms
    )

    return result
```

## 🎯 Roadmap

- [ ] Dashboard web para visualización
- [ ] Integración con Grafana
- [ ] Anomaly detection avanzado
- [ ] A/B testing support
- [ ] Model versioning tracking
- [ ] Cost monitoring
- [ ] Automated retraining triggers

## 📞 Soporte

Para issues, preguntas o contribuciones, contacta al equipo de ML Engineering.

---

**Versión**: 1.0.0
**Última actualización**: 2025-10-20
