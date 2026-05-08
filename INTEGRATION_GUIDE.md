# Guía de Integración con Servicios Existentes

Esta guía muestra cómo integrar el servicio de monitoreo con tus servicios ML existentes.

## 📦 Instalación de Cliente

Primero, agrega httpx a tus servicios:

```bash
pip install httpx
```

## 🔍 Integración con Search Service

### 1. Crear utilidad de monitoreo

Crea `search/ecommerce-semantic-search/utils/monitoring.py`:

```python
"""Monitoring utilities for ML logging."""
import httpx
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import get_settings

settings = get_settings()
MONITORING_SERVICE_URL = "http://localhost:8003/api/v1"


async def log_search_prediction(
    query: str,
    embedding: Optional[List[float]],
    results: List[Dict[str, Any]],
    latency_ms: float,
    category_filter: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    error: Optional[str] = None,
):
    """Log search prediction to monitoring service."""
    try:
        # Calculate metrics
        embedding_norm = None
        if embedding:
            embedding_array = np.array(embedding)
            embedding_norm = float(np.linalg.norm(embedding_array))

        top_score = None
        avg_score = None
        if results:
            scores = [r.get("score_semantico", 0) for r in results]
            top_score = float(max(scores)) if scores else None
            avg_score = float(np.mean(scores)) if scores else None

        payload = {
            "query": query,
            "query_length": len(query),
            "embedding_norm": embedding_norm,
            "num_results": len(results),
            "top_score": top_score,
            "avg_score": avg_score,
            "category_filter": category_filter,
            "price_min": price_min,
            "price_max": price_max,
            "latency_ms": latency_ms,
            "error": error,
        }

        # Send async request
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{MONITORING_SERVICE_URL}/predictions/search",
                json=payload
            )

    except Exception as e:
        # Don't fail the main request if monitoring fails
        print(f"Warning: Failed to log prediction to monitoring: {e}")
```

### 2. Integrar en rutas

Modifica `search/ecommerce-semantic-search/api/routes.py`:

```python
from datetime import datetime
from utils.monitoring import log_search_prediction

@router.post("/buscar")
async def buscar_productos(
    request: SearchRequest,
    es_service: ElasticsearchService = Depends(get_elasticsearch_service)
):
    """Endpoint de búsqueda semántica con monitoreo."""
    start_time = datetime.now()
    error = None
    results = []
    embedding = None

    try:
        # Búsqueda normal
        search_results = await es_service.search_products(request)
        results = search_results.get("resultados", [])

        # Opcional: Obtener embedding para monitoreo
        # embedding = await es_service.embedding_service.generate_embedding(request.query)

        return search_results

    except Exception as e:
        error = str(e)
        raise

    finally:
        # Calcular latencia
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Log a monitoreo (no bloquea el request)
        try:
            await log_search_prediction(
                query=request.query,
                embedding=embedding,  # None si no se calculó
                results=results,
                latency_ms=latency_ms,
                category_filter=request.category,
                price_min=request.price_min,
                price_max=request.price_max,
                error=error,
            )
        except:
            pass  # Silently fail
```

## 💬 Integración con Sentiment Service

### 1. Crear utilidad de monitoreo

Crea `sentiment-service/ecommerce-sentiment-service/src/utils/monitoring.py`:

```python
"""Monitoring utilities for sentiment analysis."""
import httpx
from typing import Dict, Any, Optional
from src.core.config import get_settings

settings = get_settings()
MONITORING_SERVICE_URL = "http://localhost:8003/api/v1"


async def log_sentiment_prediction(
    text: str,
    prediction_result: Dict[str, Any],
    latency_ms: float,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    rating: Optional[int] = None,
    error: Optional[str] = None,
):
    """Log sentiment prediction to monitoring service."""
    try:
        # Extract scores
        all_scores = {}
        for score_obj in prediction_result.get("all_scores", []):
            label = score_obj.get("label")
            score = score_obj.get("score")
            if label and score is not None:
                all_scores[label] = score

        payload = {
            "text": text,
            "text_length": len(text),
            "predicted_sentiment": prediction_result.get("predicted_sentiment"),
            "confidence": prediction_result.get("confidence"),
            "primary_score": prediction_result.get("primary_score"),
            "all_scores": all_scores,
            "product_id": product_id,
            "user_id": user_id,
            "rating": rating,
            "latency_ms": latency_ms,
            "error": error,
        }

        # Send async request
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{MONITORING_SERVICE_URL}/predictions/sentiment",
                json=payload
            )

    except Exception as e:
        # Don't fail the main request
        print(f"Warning: Failed to log sentiment prediction: {e}")
```

### 2. Integrar en rutas

Modifica `sentiment-service/ecommerce-sentiment-service/src/api/routes/sentiment.py`:

```python
from datetime import datetime
from src.utils.monitoring import log_sentiment_prediction

@router.post("/analyze", response_model=SentimentResponse)
async def analyze_sentiment(
    request: SentimentRequest,
    service: SentimentService = Depends(get_sentiment_service)
):
    """Analyze sentiment with monitoring."""
    start_time = datetime.now()
    error = None
    result = None

    try:
        # Análisis normal
        result = service.analyze(request.text)

        return SentimentResponse(
            text=request.text,
            **result
        )

    except Exception as e:
        error = str(e)
        raise

    finally:
        # Calcular latencia
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Log a monitoreo
        if result:
            try:
                await log_sentiment_prediction(
                    text=request.text,
                    prediction_result=result,
                    latency_ms=latency_ms,
                    error=error,
                )
            except:
                pass


@router.post("/analyze-batch")
async def analyze_sentiment_batch(
    request: BatchSentimentRequest,
    service: SentimentService = Depends(get_sentiment_service)
):
    """Analyze multiple texts with monitoring."""
    results = []

    for text in request.texts:
        start_time = datetime.now()

        try:
            result = service.analyze(text)
            results.append(result)

            # Log cada predicción
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            await log_sentiment_prediction(
                text=text,
                prediction_result=result,
                latency_ms=latency_ms,
            )

        except Exception as e:
            results.append({"error": str(e)})

    return {"results": results}
```

## 🔄 Integración con Comments Service

El Comments Service puede integrarse para enviar comentarios al Sentiment Service y loggear resultados:

```python
# comments/ecommerce-comment-service/app/services/comment_service.py

import httpx

async def analyze_comment_sentiment(comment_text: str) -> dict:
    """Analyze comment sentiment and log to monitoring."""
    async with httpx.AsyncClient() as client:
        # Call sentiment service
        response = await client.post(
            "http://localhost:8002/api/v1/analyze",
            json={"text": comment_text}
        )
        return response.json()

async def create_comment_with_sentiment(comment_data: CommentCreate) -> Comment:
    """Create comment and analyze sentiment."""
    # Create comment
    comment = comment_crud.create(db, comment_data)

    # Analyze sentiment
    sentiment_result = await analyze_comment_sentiment(comment.comment)

    # Update comment with sentiment
    comment.sentiment_label = sentiment_result["predicted_sentiment"]
    comment.sentiment_score = sentiment_result["primary_score"]

    db.commit()

    return comment
```

## ⚙️ Configuración de URLs

Asegúrate de configurar las URLs correctas en los `.env` de cada servicio:

### Search Service
```bash
MONITORING_SERVICE_URL=http://localhost:8003
```

### Sentiment Service
```bash
MONITORING_SERVICE_URL=http://localhost:8003
```

### Comments Service
```bash
SENTIMENT_SERVICE_URL=http://localhost:8002
MONITORING_SERVICE_URL=http://localhost:8003
```

## 🐳 Docker Compose

Para ejecutar todos los servicios juntos:

```yaml
version: '3.8'

services:
  search-service:
    build: ./search/ecommerce-semantic-search
    ports:
      - "8000:8000"
    environment:
      - MONITORING_SERVICE_URL=http://monitoring-service:8003

  sentiment-service:
    build: ./sentiment-service/ecommerce-sentiment-service
    ports:
      - "8002:8002"
    environment:
      - MONITORING_SERVICE_URL=http://monitoring-service:8003

  monitoring-service:
    build: ./monitoring-service/ecommerce-ml-monitoring
    ports:
      - "8003:8003"
    volumes:
      - ./monitoring-data:/app/data
    environment:
      - SEARCH_SERVICE_URL=http://search-service:8000
      - SENTIMENT_SERVICE_URL=http://sentiment-service:8002
```

## 📊 Verificar Integración

### 1. Hacer requests de prueba

```bash
# Search
curl -X POST "http://localhost:8000/api/v1/buscar" \
  -H "Content-Type: application/json" \
  -d '{"query": "laptop gaming", "top_k": 5}'

# Sentiment
curl -X POST "http://localhost:8002/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{"text": "Este producto es excelente"}'
```

### 2. Verificar logs en monitoring

```bash
# Ver stats
curl "http://localhost:8003/api/v1/predictions/search/stats?hours=1"
curl "http://localhost:8003/api/v1/predictions/sentiment/stats?hours=1"
```

### 3. Generar primer report

```bash
# Después de tener ~100 predicciones
curl -X POST "http://localhost:8003/api/v1/monitoring/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "search",
    "report_type": "comprehensive",
    "time_window_hours": 1
  }'
```

## 🔔 Configurar Alertas

### Slack
1. Crear webhook en Slack
2. Configurar en `.env`:
```bash
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
SLACK_CHANNEL=#ml-alerts
```

### Ajustar Thresholds
```bash
DRIFT_THRESHOLD=0.3
LATENCY_THRESHOLD_MS=2000
ERROR_RATE_THRESHOLD=0.05
```

## 🎯 Best Practices

1. **No bloquear requests principales**: Los logs de monitoreo deben ser async y no fallar
2. **Sampling**: Para alto volumen, considera samplear (ej: 10% de predicciones)
3. **Batch logging**: Para batch predictions, logea en bulk
4. **Error handling**: Monitoreo nunca debe causar que falle el request principal
5. **Timeouts**: Usa timeouts cortos (1-2s) para requests de logging
6. **Reference data**: Actualiza reference data semanalmente
7. **Reports automáticos**: Configura APScheduler para reports diarios

## 🐛 Troubleshooting

### Monitoreo no recibe logs
```bash
# Verificar que el servicio está corriendo
curl http://localhost:8003/health

# Ver logs del servicio
docker logs monitoring-service -f
```

### Reports fallan por datos insuficientes
```bash
# Verificar cantidad de predicciones
curl http://localhost:8003/api/v1/predictions/search/stats?hours=24

# Necesitas al menos 100 predicciones para generar reports
```

### Drift alerts constantes
```bash
# Actualizar reference data con datos recientes
curl -X POST "http://localhost:8003/api/v1/monitoring/reference-data/update" \
  -H "Content-Type: application/json" \
  -d '{"service_name": "search", "hours_to_sample": 168}'
```

---

Para más información, consulta el README principal.
