"""
Consumidor de mensajes para RabbitMQ.
Este script consume mensajes de alertas de ML monitoring desde una cola de RabbitMQ.
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


def callback(ch, method, properties, body):
    """
    Función de callback que se ejecuta cuando se recibe un mensaje.

    Args:
        ch: Canal de RabbitMQ
        method: Método de delivery
        properties: Propiedades del mensaje
        body: Cuerpo del mensaje
    """
    try:
        # Decodificar el mensaje JSON
        message = json.loads(body.decode('utf-8'))

        # Formatear la salida
        print("\n" + "="*80)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] NUEVA ALERTA RECIBIDA")
        print("="*80)

        print(f"\n📋 Tipo de Evento: {message.get('event_type', 'N/A')}")
        print(f"🏷️  Servicio: {message.get('service_name', 'N/A')}")
        print(f"⚠️  Severidad: {message.get('severity', 'N/A').upper()}")
        print(f"🆔 Alert ID: {message.get('alert_id', 'N/A')}")
        print(f"🕐 Timestamp: {message.get('timestamp', 'N/A')}")

        # Mostrar métricas según el tipo de alerta
        metrics = message.get('metrics', {})
        if metrics:
            print(f"\n📊 Métricas:")
            if 'drift_score' in metrics:
                print(f"   • Drift Score: {metrics['drift_score']:.4f}")
                print(f"   • Threshold: {metrics.get('drift_threshold', 'N/A')}")
                if 'drift_by_feature' in metrics:
                    print(f"   • Drift por Feature:")
                    for feature, score in metrics['drift_by_feature'].items():
                        print(f"      - {feature}: {score:.4f}")

            elif 'quality_score' in metrics:
                print(f"   • Quality Score: {metrics['quality_score']:.4f}")
                issues = metrics.get('issues', {})
                if issues:
                    print(f"   • Problemas de Calidad:")
                    for issue, value in issues.items():
                        print(f"      - {issue}: {value}")

            elif 'p95_latency_ms' in metrics:
                print(f"   • P95 Latency: {metrics.get('p95_latency_ms', 'N/A')} ms")
                print(f"   • P99 Latency: {metrics.get('p99_latency_ms', 'N/A')} ms")
                print(f"   • Avg Latency: {metrics.get('avg_latency_ms', 'N/A')} ms")

            elif 'error_rate' in metrics:
                print(f"   • Error Rate: {metrics.get('error_rate', 0)*100:.2f}%")
                print(f"   • Error Count: {metrics.get('error_count', 'N/A')}")
                print(f"   • Total Requests: {metrics.get('total_requests', 'N/A')}")

        print("\n" + "="*80 + "\n")

        # Confirmar el mensaje (acknowledge)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        print(f"❌ Error al decodificar JSON: {e}", file=sys.stderr)
        print(f"   Mensaje crudo: {body}", file=sys.stderr)
        # Rechazar el mensaje
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}", file=sys.stderr)
        # Rechazar el mensaje
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    """
    Función principal que conecta con RabbitMQ y consume mensajes de la cola.
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

        # Declarar cola (debe ser la misma configuración que el productor)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        print(f"✅ Cola '{QUEUE_NAME}' declarada correctamente.")

        # Configurar QoS para procesar un mensaje a la vez
        channel.basic_qos(prefetch_count=1)

        # Configurar el consumidor
        channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=callback,
            auto_ack=False  # Confirmación manual de mensajes
        )

        print(f"\n🎧 Esperando mensajes en la cola '{QUEUE_NAME}'...")
        print("   Presiona CTRL+C para salir\n")

        # Comenzar a consumir mensajes
        channel.start_consuming()

    except KeyboardInterrupt:
        print("\n\n🛑 Consumidor detenido por el usuario.")
        try:
            channel.stop_consuming()
            connection.close()
        except:
            pass
        sys.exit(0)

    except pika.exceptions.AMQPConnectionError as e:
        print(f"❌ Error de conexión con RabbitMQ: {e}", file=sys.stderr)
        print("   Asegúrate de que RabbitMQ esté ejecutándose.", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"❌ Error inesperado: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
