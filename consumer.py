import os
import json
import threading
import urllib.request
import pika
from matching_service.matching import (
    DonationInfo,
    NGOProfile,
    find_best_matches,
)
from matching_service.grpc_client import InventoryServiceClient
from donation_service.rabbitmq import publish_donation_matched, publish_donation_reserved

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
EXCHANGE_NAME = "food_events"
MATCHING_QUEUE = "matching_queue"

INVENTORY_HOST = os.getenv("INVENTORY_HOST", "localhost")
INVENTORY_PORT = int(os.getenv("INVENTORY_PORT", "8004"))
inventory_client = InventoryServiceClient(host=INVENTORY_HOST, port=INVENTORY_PORT)

match_results_cache: dict[str, list[dict]] = {}
pending_matches: list[dict] = []

sample_ngos = [
    NGOProfile(
        user_id="NGO-001",
        name="Hope Foundation",
        latitude=28.6139,
        longitude=77.2090,
        accepted_food_types=["cooked", "packaged", "fresh", "vegetarian", "vegan", "any"],
        priority_score=85.0,
        capacity_remaining=200.0,
    ),
    NGOProfile(
        user_id="NGO-002",
        name="Feed the Hungry",
        latitude=28.6200,
        longitude=77.2150,
        accepted_food_types=["cooked", "packaged", "grains", "any"],
        priority_score=90.0,
        capacity_remaining=150.0,
    ),
    NGOProfile(
        user_id="NGO-003",
        name="Food Bank Initiative",
        latitude=28.6300,
        longitude=77.2200,
        accepted_food_types=["fresh", "vegetables", "fruits", "packaged", "any"],
        priority_score=70.0,
        capacity_remaining=300.0,
    ),
    NGOProfile(
        user_id="NGO-004",
        name="Community Kitchen",
        latitude=28.6050,
        longitude=77.1950,
        accepted_food_types=["cooked", "vegetarian", "vegan", "any"],
        priority_score=75.0,
        capacity_remaining=100.0,
    ),
    NGOProfile(
        user_id="NGO-005",
        name="Zero Waste Alliance",
        latitude=28.6400,
        longitude=77.2300,
        accepted_food_types=["packaged", "canned", "dry", "any"],
        priority_score=60.0,
        capacity_remaining=500.0,
    ),
]


def run_matching_for_donation(donation_data: dict) -> list[dict]:
    donation = DonationInfo(
        donation_id=donation_data["donation_id"],
        food_type=donation_data.get("food_type", "general"),
        food_name=donation_data.get("food_name", ""),
        quantity=donation_data.get("quantity", 0.0),
        unit=donation_data.get("unit", "kg"),
        latitude=donation_data.get("latitude"),
        longitude=donation_data.get("longitude"),
    )

    matches = find_best_matches(donation, sample_ngos, top_n=5)

    results = []
    for match in matches:
        availability = inventory_client.check_availability(match.donation_id)
        result = {
            "ngo_id": match.ngo_id,
            "ngo_name": match.ngo_name,
            "donation_id": match.donation_id,
            "score": match.score,
            "distance_km": match.distance_km,
            "food_type_match": match.food_type_match,
            "quantity_match": match.quantity_match,
            "inventory_available": availability.get("available", False),
            "inventory_quantity": availability.get("quantity", 0.0),
        }
        results.append(result)

    match_results_cache[donation.donation_id] = results

    best_match = results[0] if results else None
    if best_match and best_match["inventory_available"]:
        reservation = inventory_client.reserve_donation(
            donation.donation_id, best_match["ngo_id"]
        )
        best_match["reservation"] = reservation

        if reservation.get("success"):
            try:
                don_status_url = "http://localhost:8002/donations/{}".format(donation.donation_id)
                don_payload = json.dumps({"status": "RESERVED"}).encode()
                don_req = urllib.request.Request(
                    don_status_url, data=don_payload,
                    headers={"Content-Type": "application/json"}, method="PUT",
                )
                urllib.request.urlopen(don_req, timeout=5)
            except Exception:
                pass

            try:
                publish_donation_reserved({
                    "donation_id": donation.donation_id,
                    "ngo_id": best_match["ngo_id"],
                    "ngo_name": best_match["ngo_name"],
                    "score": best_match["score"],
                })
            except Exception as e:
                print(f"Warning: Could not publish reservation event: {e}")

    try:
        publish_donation_matched({
            "donation_id": donation.donation_id,
            "matches_count": len(results),
            "best_match_ngo_id": best_match["ngo_id"] if best_match else None,
            "best_match_score": best_match["score"] if best_match else 0.0,
        })
    except Exception as e:
        print(f"Warning: Could not publish match event: {e}")

    return results


def process_message(ch, method, properties, body):
    try:
        message = json.loads(body.decode())
        event = message.get("event", "")
        data = message.get("data", {})

        if event == "DonationCreated":
            print(f"Processing matching for donation: {data.get('donation_id')}")
            results = run_matching_for_donation(data)
            print(f"Found {len(results)} matches for donation {data.get('donation_id')}")
        else:
            print(f"Unhandled event in matching_queue: {event}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                    socket_timeout=2, connection_attempts=1, retry_delay=0,
                )
            )
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
            channel.queue_declare(queue=MATCHING_QUEUE, durable=True)
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=MATCHING_QUEUE, routing_key="donation.created")
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=MATCHING_QUEUE, on_message_callback=process_message)

            print("Matching service consumer started. Waiting for messages...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ not available. Retrying in 5 seconds...")
            import time
            time.sleep(5)
        except Exception as e:
            print(f"Consumer error: {e}. Retrying in 5 seconds...")
            import time
            time.sleep(5)


def start_consumer_thread():
    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
    print("Matching consumer thread started")
    return thread
