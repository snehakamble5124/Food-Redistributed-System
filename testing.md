# Testing Guide - Distributed Food Waste Redistribution System

## Overview

This document covers 10 comprehensive test scenarios that validate all major features of the system including user management, donations, matching, delivery, distributed algorithms, and service communication.

---

## Prerequisites

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Wait for services to be healthy
docker-compose -f docker/docker-compose.yml ps

# Verify database is seeded
psql -h localhost -U postgres -d food_waste_db -c "SELECT COUNT(*) FROM users;"
```

---

## Test 1: User Registration and Authentication

### Objective
Verify that users can register with different roles and authenticate via JWT.

### Steps
```bash
# Register a Donor
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "DONOR-TEST-001",
    "name": "Test Restaurant",
    "email": "testrestaurant@email.com",
    "password": "password123",
    "role": "DONOR",
    "phone": "+1-555-9999",
    "latitude": 40.7128,
    "longitude": -74.0060
  }'

# Register an NGO
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "NGO-TEST-001",
    "name": "Test NGO",
    "email": "testngo@email.com",
    "password": "password123",
    "role": "NGO",
    "phone": "+1-555-8888",
    "latitude": 40.7589,
    "longitude": -73.9851
  }'

# Login as Donor
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testrestaurant@email.com", "password": "password123"}'

# Login as NGO
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testngo@email.com", "password": "password123"}'
```

### Expected Results
- Registration returns 201 with user data (no password hash in response)
- Login returns 200 with JWT access_token and user info
- Invalid credentials return 401
- Duplicate email returns 409
- Store JWT tokens for subsequent tests: `export DONOR_TOKEN=<token>` and `export NGO_TOKEN=<token>`

---

## Test 2: Food Donation Creation and Management

### Objective
Verify donors can create, view, update, and cancel donations with proper Lamport and Vector clock tracking.

### Steps
```bash
# Create a donation
curl -X POST http://localhost:8002/donations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DONOR_TOKEN" \
  -d '{
    "food_name": "Pasta Primavera",
    "food_type": "cooked_meal",
    "quantity": 30.0,
    "unit": "kg",
    "prepared_at": "2025-01-15T08:00:00Z",
    "expiry_time": "2025-01-16T08:00:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060
  }'

# View all available donations
curl http://localhost:8002/donations/available

# View specific donation
curl http://localhost:8002/donations/DON-TEST-001

# Check distributed events for clock tracking
curl http://localhost:8002/events
```

### Expected Results
- Donation created with status "AVAILABLE" and initial Lamport timestamp = 1
- Vector timestamp contains the donation service counter
- Available donations list includes the new donation
- Event log shows DONATION_CREATED event with correct timestamps

---

## Test 3: NGO Requirement Creation and Matching

### Objective
Verify NGOs can set food requirements and the matching algorithm pairs them with suitable donations.

### Steps
```bash
# Create NGO requirement
curl -X POST http://localhost:8003/requirements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $NGO_TOKEN" \
  -d '{
    "food_type": "cooked_meal",
    "required_quantity": 20.0,
    "priority": 1
  }'

# Trigger matching algorithm
curl -X POST http://localhost:8003/matching/run

# View match results
curl http://localhost:8003/matching/results
```

### Expected Results
- Requirement created with correct food type and priority
- Matching algorithm finds Pasta Primavera (30 kg, cooked_meal) matches the requirement
- Match result includes match_score based on food type, quantity, and proximity
- Distributed events show MATCH_FOUND with vector timestamps

---

## Test 4: Inventory Reservation via gRPC

### Objective
Verify the Inventory Service gRPC interface correctly handles availability checks and reservations.

### Steps
```bash
# Check availability via REST
curl http://localhost:8004/inventory/DON-TEST-001

# Check availability via gRPC (using grpcurl or test client)
grpcurl -plaintext -d '{"donation_id": "DON-TEST-001"}' \
  localhost:50051 inventory.InventoryService/CheckAvailability

# Reserve donation
grpcurl -plaintext -d '{
  "donation_id": "DON-TEST-001",
  "ngo_id": "NGO-TEST-001",
  "lamport_timestamp": 3,
  "vector_timestamp": {"SVC-INVENTORY": 1}
}' localhost:50051 inventory.InventoryService/ReserveDonation

# Verify reservation
curl http://localhost:8004/inventory/DON-TEST-001
```

### Expected Results
- CheckAvailability returns available=true, quantity=30.0, status="AVAILABLE"
- ReserveDonation returns success=true, message="Donation reserved successfully"
- New Lamport timestamp is incremented (4)
- Vector timestamp is merged and incremented
- Subsequent availability check shows status="RESERVED"

---

## Test 5: Delivery Assignment and Tracking

### Objective
Verify delivery creation, volunteer assignment, and status tracking through the full lifecycle.

### Steps
```bash
# Create delivery (typically auto-created by matching)
curl -X POST http://localhost:8005/deliveries \
  -H "Content-Type: application/json" \
  -d '{
    "donation_id": "DON-TEST-001",
    "ngo_id": "NGO-TEST-001",
    "pickup_lat": 40.7128,
    "pickup_lng": -74.0060,
    "drop_lat": 40.7589,
    "drop_lng": -73.9851
  }'

# View active deliveries for volunteer
curl http://localhost:8005/deliveries/active/VOL-001

# Update status to PICKED_UP
curl -X PUT http://localhost:8005/deliveries/DEL-TEST-001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "PICKED_UP"}'

# Update status to IN_TRANSIT
curl -X PUT http://localhost:8005/deliveries/DEL-TEST-001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "IN_TRANSIT"}'

# Complete delivery
curl -X PUT http://localhost:8005/deliveries/DEL-TEST-001/complete

# Check final status
curl http://localhost:8005/deliveries/DEL-TEST-001
```

### Expected Results
- Delivery created with status "ASSIGNED"
- Status transitions: ASSIGNED -> PICKED_UP -> IN_TRANSIT -> DELIVERED
- completed_at timestamp is set on completion
- Donation status updates to "DELIVERED"

---

## Test 6: Real-Time Notifications via WebSocket

### Objective
Verify WebSocket connections receive real-time push notifications.

### Steps
```bash
# Connect WebSocket client (using wscat)
wscat -c ws://localhost:8006/ws/NGO-TEST-001

# In another terminal, trigger a notification by creating a donation
curl -X POST http://localhost:8002/donations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DONOR_TOKEN" \
  -d '{
    "food_name": "Fresh Fruits",
    "food_type": "produce",
    "quantity": 10.0,
    "unit": "kg",
    "expiry_time": "2025-01-17T08:00:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060
  }'
```

### Expected Results
- WebSocket connection established successfully
- When donation is created, connected client receives notification JSON:
  ```json
  {
    "type": "new_donation",
    "title": "New Donation Available",
    "message": "Fresh Fruits (10 kg) available for matching",
    "timestamp": "2025-01-15T10:30:00Z"
  }
  ```
- Notifications are persisted in the database

---

## Test 7: Lamport Clock Consistency

### Objective
Verify Lamport timestamps are correctly maintained across service interactions.

### Steps
```bash
# Create donation (should get Lamport timestamp = 1)
curl -X POST http://localhost:8002/donations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DONOR_TOKEN" \
  -d '{
    "food_name": "Soup",
    "food_type": "cooked_meal",
    "quantity": 15.0,
    "unit": "kg",
    "expiry_time": "2025-01-16T08:00:00Z",
    "latitude": 40.7128,
    "longitude": -74.0060
  }'

# Check inventory (gRPC call should increment clock)
grpcurl -plaintext -d '{"donation_id": "DON-LAMP-001"}' \
  localhost:50051 inventory.InventoryService/CheckAvailability

# View distributed events to verify timestamps
curl http://localhost:8002/events
curl http://localhost:8004/events
```

### Expected Results
- Each service increments its Lamport counter on local events
- Cross-service communication causes receiver to take max(local, received) + 1
- Events in distributed_events table show monotonically increasing timestamps per service
- Global ordering is consistent with the happened-before relation

---

## Test 8: Vector Clock Causality Detection

### Objective
Verify vector clocks correctly track causal relationships and detect concurrency.

### Steps
```bash
# Create two donations concurrently
curl -X POST http://localhost:8002/donations -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DONOR_TOKEN" \
  -d '{"food_name": "Rice", "food_type": "grain", "quantity": 20.0, "unit": "kg", "expiry_time": "2025-01-17T08:00:00Z", "latitude": 40.7128, "longitude": -74.0060}' &

curl -X POST http://localhost:8002/donations -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DONOR_TOKEN" \
  -d '{"food_name": "Bread", "food_type": "bakery", "quantity": 10.0, "unit": "kg", "expiry_time": "2025-01-16T08:00:00Z", "latitude": 40.7128, "longitude": -74.0060}' &

# Check vector timestamps
curl http://localhost:8002/donations | python3 -m json.tool

# Query concurrency detection
curl "http://localhost:8002/events/concurrency"
```

### Expected Results
- Both donations have vector timestamps where SVC-DONATION counter differs
- The vector timestamps show concurrent events (neither dominates)
- The system correctly identifies that the two creations are causally independent

---

## Test 9: Service Health and Heartbeat Monitoring

### Objective
Verify service registry, heartbeat mechanism, and failure detection.

### Steps
```bash
# Check all services are UP
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
curl http://localhost:8006/health

# View services registry
psql -h localhost -U postgres -d food_waste_db \
  -c "SELECT * FROM services_registry;"

# Stop a service to test failure detection
docker stop fwr-matching-service

# Wait for heartbeat timeout (30-60 seconds)
# Check that matching service is marked DOWN
psql -h localhost -U postgres -d food_waste_db \
  -c "SELECT * FROM services_registry WHERE service_id = 'SVC-MATCHING';"

# Restart and verify recovery
docker start fwr-matching-service
sleep 30
psql -h localhost -U postgres -d food_waste_db \
  -c "SELECT * FROM services_registry WHERE service_id = 'SVC-MATCHING';"
```

### Expected Results
- All 6 services return healthy status initially
- services_registry table shows all with status="UP" and recent heartbeats
- After stopping matching service, its status changes to "DOWN" after heartbeat timeout
- After restart, status returns to "UP" within one heartbeat interval

---

## Test 10: Chandy-Lamport Snapshot and Global State

### Objective
Verify the system can capture a consistent global snapshot across all services.

### Steps
```bash
# Create some donations and deliveries first (to populate state)
curl -X POST http://localhost:8002/donations ...  # Create 2-3 donations
curl -X POST http://localhost:8003/requirements ... # Create 1 requirement

# Trigger snapshot
curl -X POST http://localhost:8004/snapshot

# View snapshot results
curl http://localhost:8004/snapshot/latest

# Verify consistency: check that captured states are from the same logical time
curl http://localhost:8004/snapshot/latest | python3 -m json.tool
```

### Expected Results
- Snapshot captures all service states in a consistent manner
- Each service's state is recorded at a point that is causally consistent with others
- Marker messages are exchanged on all channels
- Snapshot includes:
  - Donation service: count of available, reserved, expired donations
  - Inventory service: active reservations and locks
  - Matching service: pending and completed matches
  - Delivery service: active deliveries
- All states reference Lamport timestamps that are mutually consistent

---

## Additional Testing Commands

### Full Test Suite Run
```bash
# Run all curl-based tests sequentially
echo "=== Test 1: User Registration ==="
# ... (paste test 1 commands)

echo "=== Test 2: Donation Creation ==="
# ... (paste test 2 commands)

# Continue for all 10 tests
```

### Docker Service Logs for Debugging
```bash
docker-compose -f docker/docker-compose.yml logs user-service
docker-compose -f docker/docker-compose.yml logs donation-service
docker-compose -f docker/docker-compose.yml logs matching-service
docker-compose -f docker/docker-compose.yml logs inventory-service
docker-compose -f docker/docker-compose.yml logs delivery-service
docker-compose -f docker/docker-compose.yml logs notification-service
```

### Database Verification Queries
```bash
psql -h localhost -U postgres -d food_waste_db -c "SELECT * FROM distributed_events ORDER BY lamport_timestamp;"
psql -h localhost -U postgres -d food_waste_db -c "SELECT donation_id, status, lamport_timestamp FROM donations;"
psql -h localhost -U postgres -d food_waste_db -c "SELECT * FROM deliveries;"
```

### Cleanup Between Tests
```bash
psql -h localhost -U postgres -d food_waste_db -c "DELETE FROM distributed_events;"
psql -h localhost -U postgres -d food_waste_db -c "DELETE FROM deliveries;"
psql -h localhost -U postgres -d food_waste_db -c "DELETE FROM donations WHERE donation_id LIKE 'DON-TEST%';"
psql -h localhost -U postgres -d food_waste_db -c "DELETE FROM users WHERE user_id LIKE '%TEST%';"
```
