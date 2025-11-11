"""
Productor de mensajes de prueba para RabbitMQ.
Este script envía mensajes de prueba simulando alertas de ML monitoring.
"""
import pika
import sys
import json
from datetime import datetime


# Configuración de RabbitMQ
RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "guest"
RABBITMQ_PASSWORD = "guest"
QUEUE_NAME = "ml_monitoring_alerts"


def create_drift_alert_message(service_name: str, drift_score: float):
    """Crear mensaje de alerta de data drift."""
    return {
        "event_type": "data_drift_detected",
        "timestamp": datetime.utcnow().isoformat(),
        "service_name": service_name,
        "alert_id": f"test-drift-{datetime.utcnow().timestamp()}",
        "severity": "critical" if drift_score > 0.5 else "warning",
        "metrics": {
            "drift_score": drift_score,
            "drift_threshold": 0.3,
            "drift_by_feature": {
                "query_length": 0.45,
                "embedding_norm": 0.38,
                "num_results": 0.12,
                "latency_ms": 0.25
            }
        }
    }


def create_performance_alert_message(service_name: str, latency_ms: float):
    """Crear mensaje de alerta de performance."""
    return {
        "event_type": "performance_alert",
        "timestamp": datetime.utcnow().isoformat(),
        "service_name": service_name,
        "alert_id": f"test-perf-{datetime.utcnow().timestamp()}",
        "severity": "critical" if latency_ms > 4000 else "warning",
        "metrics": {
            "p95_latency_ms": latency_ms,
            "p99_latency_ms": latency_ms * 1.2,
            "avg_latency_ms": latency_ms * 0.7
        }
    }


def create_data_quality_alert_message(service_name: str, quality_score: float):
    """Crear mensaje de alerta de calidad de datos."""
    return {
        "event_type": "data_quality_alert",
        "timestamp": datetime.utcnow().isoformat(),
        "service_name": service_name,
        "alert_id": f"test-quality-{datetime.utcnow().timestamp()}",
        "severity": "critical" if quality_score < 0.6 else "warning",
        "metrics": {
            "quality_score": quality_score,
            "issues": {
                "missing_values_percentage": 15.5,
                "duplicates_count": 42,
                "out_of_range_count": 8
            }
        }
    }


def main():
    """
    Función principal que conecta con RabbitMQ y envía mensajes de prueba.
    """
    try:
        # Configurar credenciales
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)

        # Configurar parámetros de conexión
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )

        # Establecer conexión
        print(f"🔌 Conectando a RabbitMQ en {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Declarar cola (durable para que persista los mensajes)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        print(f"✅ Cola '{QUEUE_NAME}' declarada correctamente.\n")

        # Mensajes de prueba
        test_messages = [
            ("Data Drift - Search Service", create_drift_alert_message("search", 0.45)),
            ("Data Drift - Sentiment Service", create_drift_alert_message("sentiment", 0.62)),
            ("High Latency - Search Service", create_performance_alert_message("search", 2500)),
            ("High Latency - Sentiment Service", create_performance_alert_message("sentiment", 4500)),
            ("Data Quality - Search Service", create_data_quality_alert_message("search", 0.72)),
            ("Data Quality - Sentiment Service", create_data_quality_alert_message("sentiment", 0.55)),
        ]

        # Enviar mensajes de prueba
        print("📤 Enviando mensajes de prueba...\n")
        for i, (description, message) in enumerate(test_messages, 1):
            # Convertir mensaje a JSON
            message_body = json.dumps(message, default=str)

            # Publicar mensaje (delivery_mode=2 hace el mensaje persistente)
            channel.basic_publish(
                exchange='',
                routing_key=QUEUE_NAME,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # hace el mensaje persistente
                    content_type='application/json',
                    timestamp=int(datetime.utcnow().timestamp()),
                )
            )

            print(f"✅ [{i}/{len(test_messages)}] Enviado: {description}")
            print(f"   • Tipo: {message['event_type']}")
            print(f"   • Servicio: {message['service_name']}")
            print(f"   • Severidad: {message['severity']}")
            print()

        print(f"\n🎉 ¡Todos los mensajes fueron enviados exitosamente!")
        print(f"📊 Total de mensajes enviados: {len(test_messages)}")

        # Cerrar conexión
        connection.close()
        print("\n🔌 Conexión cerrada.")

    except pika.exceptions.AMQPConnectionError as e:
        print(f"❌ Error de conexión con RabbitMQ: {e}", file=sys.stderr)
        print("   Asegúrate de que RabbitMQ esté ejecutándose.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
