import os
import json
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
EXCHANGE_NAME = "food_events"
ROUTING_KEY_CREATED = "donation.created"
ROUTING_KEY_MATCHED = "donation.matched"
ROUTING_KEY_RESERVED = "donation.reserved"
ROUTING_KEY_DELIVERY = "delivery.assigned"
ROUTING_KEY_NOTIFICATION = "notification.send"


def get_connection():
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        heartbeat=600,
        blocked_connection_timeout=10,
        connection_attempts=1,
        retry_delay=0,
        socket_timeout=2,
    )
    return pika.BlockingConnection(params)


def ensure_exchange_and_queues():
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

        channel.queue_declare(queue="matching_queue", durable=True)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="matching_queue", routing_key=ROUTING_KEY_CREATED)

        channel.queue_declare(queue="notification_queue", durable=True)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="notification_queue", routing_key="donation.created")
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="notification_queue", routing_key="donation.matched")
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="notification_queue", routing_key="donation.reserved")
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="notification_queue", routing_key="notification.send")

        channel.queue_declare(queue="delivery_queue", durable=True)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="delivery_queue", routing_key=ROUTING_KEY_DELIVERY)

        channel.close()
        connection.close()
    except Exception as e:
        print(f"Warning: Could not setup RabbitMQ exchange/queues: {e}")


def publish_message(routing_key: str, message: dict):
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        connection.close()
    except Exception as e:
        print(f"Warning: RabbitMQ not available, message not sent: {e}")


def publish_donation_created(donation_data: dict):
    message = {
        "event": "DonationCreated",
        "data": donation_data,
    }
    publish_message(ROUTING_KEY_CREATED, message)


def publish_donation_matched(match_data: dict):
    message = {
        "event": "DonationMatched",
        "data": match_data,
    }
    publish_message(ROUTING_KEY_MATCHED, message)


def publish_donation_reserved(reserve_data: dict):
    message = {
        "event": "DonationReserved",
        "data": reserve_data,
    }
    publish_message(ROUTING_KEY_RESERVED, message)


def publish_delivery_assigned(delivery_data: dict):
    message = {
        "event": "VolunteerAssigned",
        "data": delivery_data,
    }
    publish_message(ROUTING_KEY_DELIVERY, message)


def publish_notification(notification_data: dict):
    message = {
        "event": "NotificationSend",
        "data": notification_data,
    }
    publish_message(ROUTING_KEY_NOTIFICATION, message)


try:
    ensure_exchange_and_queues()
except Exception:
    pass
