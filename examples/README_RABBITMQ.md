# RabbitMQ Integration para ML Monitoring

Este directorio contiene scripts de ejemplo para trabajar con la integración de RabbitMQ en el servicio de monitoreo de ML.

## Descripción General

El servicio de monitoreo publica eventos automáticamente a RabbitMQ cuando detecta:
- **Data Drift**: Desviación en la distribución de datos
- **Problemas de Performance**: Alta latencia o tasa de errores
- **Problemas de Calidad de Datos**: Valores faltantes, duplicados, etc.

## Configuración de RabbitMQ

### 1. Iniciar RabbitMQ con Docker Compose

Asegúrate de que RabbitMQ esté ejecutándose:

```bash
# Desde el directorio raíz del proyecto integrador
cd /home/santiago/Desktop/personal/udea/integrador
docker-compose up -d rabbitmq
```

### 2. Verificar que RabbitMQ está funcionando

```bash
# Verificar el contenedor
docker ps | grep rabbitmq

# Acceder a la interfaz web de RabbitMQ
# URL: http://localhost:15672
# Usuario: guest
# Password: guest
```

### 3. Configuración en el Servicio de Monitoreo

El archivo `src/core/config.py` contiene la configuración de RabbitMQ:

```python
# RabbitMQ Configuration
rabbitmq_enabled: bool = True
rabbitmq_host: str = "localhost"
rabbitmq_port: int = 5672
rabbitmq_user: str = "guest"
rabbitmq_password: str = "guest"
rabbitmq_queue_name: str = "ml_monitoring_alerts"
```

Puedes sobrescribir estos valores usando variables de entorno en un archivo `.env`:

```env
RABBITMQ_ENABLED=true
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_QUEUE_NAME=ml_monitoring_alerts
```

## Scripts de Ejemplo

### 1. Consumidor de Mensajes (`rabbitmq_consumer.py`)

Este script consume y muestra los mensajes de alertas publicados por el servicio de monitoreo.

**Uso:**
```bash
# Desde el directorio del proyecto
python examples/rabbitmq_consumer.py
```

**Características:**
- Consume mensajes de la cola `ml_monitoring_alerts`
- Muestra alertas formateadas en la consola
- Confirma automáticamente los mensajes procesados
- Maneja errores de formato JSON

**Ejemplo de salida:**
```
================================================================================
[2025-11-06 10:30:45] NUEVA ALERTA RECIBIDA
================================================================================

📋 Tipo de Evento: data_drift_detected
🏷️  Servicio: search
⚠️  Severidad: CRITICAL
🆔 Alert ID: abc123-xyz
🕐 Timestamp: 2025-11-06T10:30:45.123456

📊 Métricas:
   • Drift Score: 0.4500
   • Threshold: 0.3000
   • Drift por Feature:
      - query_length: 0.4500
      - embedding_norm: 0.3800
      - num_results: 0.1200
```

### 2. Productor de Prueba (`rabbitmq_test_producer.py`)

Este script envía mensajes de prueba simulando diferentes tipos de alertas.

**Uso:**
```bash
# Desde el directorio del proyecto
python examples/rabbitmq_test_producer.py
```

**Características:**
- Envía 6 mensajes de prueba con diferentes tipos de alertas
- Simula alertas de drift, performance y calidad de datos
- Útil para probar el consumidor y la integración

**Tipos de mensajes que envía:**
1. Data Drift - Search Service
2. Data Drift - Sentiment Service
3. High Latency - Search Service
4. High Latency - Sentiment Service
5. Data Quality - Search Service
6. Data Quality - Sentiment Service

## Formato de Mensajes

### Alerta de Data Drift

```json
{
  "event_type": "data_drift_detected",
  "timestamp": "2025-11-06T10:30:45.123456",
  "service_name": "search",
  "alert_id": "abc123-xyz",
  "severity": "critical",
  "metrics": {
    "drift_score": 0.45,
    "drift_threshold": 0.3,
    "drift_by_feature": {
      "query_length": 0.45,
      "embedding_norm": 0.38,
      "num_results": 0.12,
      "latency_ms": 0.25
    }
  }
}
```

### Alerta de Performance

```json
{
  "event_type": "performance_alert",
  "timestamp": "2025-11-06T10:30:45.123456",
  "service_name": "search",
  "alert_id": "abc123-xyz",
  "severity": "warning",
  "metrics": {
    "p95_latency_ms": 2500,
    "p99_latency_ms": 3000,
    "avg_latency_ms": 1800
  }
}
```

### Alerta de Calidad de Datos

```json
{
  "event_type": "data_quality_alert",
  "timestamp": "2025-11-06T10:30:45.123456",
  "service_name": "sentiment",
  "alert_id": "abc123-xyz",
  "severity": "warning",
  "metrics": {
    "quality_score": 0.72,
    "issues": {
      "missing_values_percentage": 15.5,
      "duplicates_count": 42,
      "out_of_range_count": 8
    }
  }
}
```

## Flujo de Trabajo

1. **Detección Automática**: El servicio de monitoreo detecta anomalías (drift, latencia, etc.)
2. **Creación de Alerta**: Se crea una alerta en la base de datos
3. **Publicación a RabbitMQ**: La alerta se publica automáticamente a RabbitMQ
4. **Consumo**: Otros servicios/aplicaciones pueden consumir estos eventos

## Integración con Otros Servicios

Puedes crear consumidores personalizados en cualquier lenguaje que soporte RabbitMQ:

### Python
```python
import pika
import json

connection = pika.BlockingConnection(
    pika.ConnectionParameters('localhost', 5672)
)
channel = connection.channel()
channel.queue_declare(queue='ml_monitoring_alerts', durable=True)

def callback(ch, method, properties, body):
    alert = json.loads(body)
    # Procesar la alerta
    print(f"Nueva alerta: {alert['event_type']}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(
    queue='ml_monitoring_alerts',
    on_message_callback=callback
)
channel.start_consuming()
```

### Node.js
```javascript
const amqp = require('amqplib');

async function consume() {
  const connection = await amqp.connect('amqp://localhost:5672');
  const channel = await connection.createChannel();
  await channel.assertQueue('ml_monitoring_alerts', { durable: true });

  channel.consume('ml_monitoring_alerts', (msg) => {
    const alert = JSON.parse(msg.content.toString());
    console.log('Nueva alerta:', alert.event_type);
    channel.ack(msg);
  });
}

consume();
```

## Monitoreo de la Cola

### Ver mensajes en la cola (interfaz web)
1. Accede a http://localhost:15672
2. Ve a la pestaña "Queues"
3. Haz clic en "ml_monitoring_alerts"
4. Puedes ver estadísticas, mensajes pendientes, etc.

### Comandos útiles

```bash
# Ver todas las colas
docker exec -it <rabbitmq-container> rabbitmqctl list_queues

# Ver consumidores conectados
docker exec -it <rabbitmq-container> rabbitmqctl list_consumers

# Purgar la cola (eliminar todos los mensajes)
docker exec -it <rabbitmq-container> rabbitmqctl purge_queue ml_monitoring_alerts
```

## Solución de Problemas

### Error de conexión a RabbitMQ

**Problema**: `AMQPConnectionError: Connection refused`

**Soluciones**:
1. Verifica que RabbitMQ esté ejecutándose: `docker ps | grep rabbitmq`
2. Verifica el puerto: Debe ser 5672 (no 15672, que es la interfaz web)
3. Verifica las credenciales en la configuración

### Mensajes no se están consumiendo

**Problema**: Los mensajes se acumulan en la cola pero no se procesan

**Soluciones**:
1. Verifica que el consumidor esté ejecutándose
2. Verifica que el nombre de la cola sea correcto
3. Revisa los logs del consumidor para errores

### Mensajes con formato incorrecto

**Problema**: Error al decodificar JSON

**Soluciones**:
1. Verifica que el mensaje sea JSON válido
2. Revisa los logs del productor
3. Usa la interfaz web de RabbitMQ para inspeccionar mensajes

## Referencias

- [Documentación de RabbitMQ](https://www.rabbitmq.com/documentation.html)
- [Pika (Python Client)](https://pika.readthedocs.io/)
- [RabbitMQ Management UI](https://www.rabbitmq.com/management.html)
