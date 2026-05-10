"""RabbitMQ consumer — recibe predicciones de sentiment y search y las persiste en DB."""
import json
import asyncio
import threading
from typing import Optional

import pika
import pika.exceptions

from src.core.config import get_settings
from src.core.logging_config import get_logger
from src.models.schemas import SentimentPredictionLog, SearchPredictionLog
from src.services.prediction_logger import PredictionLoggerService
from src.storage.database import get_db

settings = get_settings()
logger = get_logger(__name__)

SENTIMENT_QUEUE = "predictions.sentiment"
SEARCH_QUEUE = "predictions.search"


class PredictionConsumer:
    """
    Consumidor RabbitMQ que corre en un hilo daemon.

    Suscribe a predictions.sentiment y predictions.search.
    Cuando llega un mensaje, lo persiste en la BD usando el event loop
    principal de FastAPI vía asyncio.run_coroutine_threadsafe.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._thread: Optional[threading.Thread] = None
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel = None
        self._logger_service = PredictionLoggerService()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="rabbitmq-consumer", daemon=True)
        self._thread.start()
        logger.info("rabbitmq_consumer_started", queues=[SENTIMENT_QUEUE, SEARCH_QUEUE])

    def stop(self) -> None:
        try:
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception as e:
            logger.warning("rabbitmq_consumer_stop_error", error=str(e))
        logger.info("rabbitmq_consumer_stopped")

    # ── Internal ─────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        credentials = pika.PlainCredentials(
            settings.rabbitmq_user,
            settings.rabbitmq_password,
        )
        params = pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=5,
            retry_delay=3,
        )
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()

        self._channel.queue_declare(queue=SENTIMENT_QUEUE, durable=True)
        self._channel.queue_declare(queue=SEARCH_QUEUE, durable=True)
        self._channel.basic_qos(prefetch_count=10)

        self._channel.basic_consume(
            queue=SENTIMENT_QUEUE,
            on_message_callback=self._on_sentiment,
        )
        self._channel.basic_consume(
            queue=SEARCH_QUEUE,
            on_message_callback=self._on_search,
        )

        logger.info(
            "rabbitmq_consumer_connected",
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
        )

    def _run(self) -> None:
        """Bucle principal del hilo consumer."""
        while True:
            try:
                self._connect()
                self._channel.start_consuming()
            except pika.exceptions.AMQPConnectionError as e:
                logger.warning("rabbitmq_consumer_reconnecting", error=str(e))
                import time
                time.sleep(5)
            except Exception as e:
                logger.error("rabbitmq_consumer_error", error=str(e))
                import time
                time.sleep(5)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_sentiment(self, ch, method, _props, body: bytes) -> None:
        try:
            data = json.loads(body)
            future = asyncio.run_coroutine_threadsafe(
                self._save_sentiment(data), self._loop
            )
            future.result(timeout=15)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("rabbitmq_sentiment_handler_error", error=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _on_search(self, ch, method, _props, body: bytes) -> None:
        try:
            data = json.loads(body)
            future = asyncio.run_coroutine_threadsafe(
                self._save_search(data), self._loop
            )
            future.result(timeout=15)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("rabbitmq_search_handler_error", error=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # ── DB persistence ───────────────────────────────────────────────────────

    async def _save_sentiment(self, data: dict) -> None:
        prediction = SentimentPredictionLog(**data)
        async for db in get_db():
            await self._logger_service.log_sentiment_prediction(db, prediction)
            logger.info(
                "sentiment_prediction_saved_from_queue",
                sentiment=data.get("predicted_sentiment"),
            )
            return

    async def _save_search(self, data: dict) -> None:
        prediction = SearchPredictionLog(**data)
        async for db in get_db():
            await self._logger_service.log_search_prediction(db, prediction)
            logger.info(
                "search_prediction_saved_from_queue",
                num_results=data.get("num_results"),
            )
            return


# ── Singleton ────────────────────────────────────────────────────────────────

_consumer: Optional[PredictionConsumer] = None


def get_prediction_consumer(loop: asyncio.AbstractEventLoop) -> PredictionConsumer:
    global _consumer
    if _consumer is None:
        _consumer = PredictionConsumer(loop)
    return _consumer
