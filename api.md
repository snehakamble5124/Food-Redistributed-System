# API Documentation - Distributed Food Waste Redistribution System

## Base URLs
- User Service: http://localhost:8001
- Donation Service: http://localhost:8002
- Matching Service: http://localhost:8003
- Inventory Service: http://localhost:8004
- Delivery Service: http://localhost:8005
- Notification Service: http://localhost:8006

## Authentication
All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

---

## 1. User Service (Port 8001)

### POST /auth/register
Register a new user.
```json
Request:
{
  "user_id": "DONOR-002",
  "name": "Pizza Palace",
  "email": "pizza@email.com",
  "password": "securepass123",
  "role": "DONOR",
  "phone": "+1-555-0199",
  "latitude": 40.7300,
  "longitude": -73.9950
}

Response (201):
{
  "message": "User registered successfully",
  "user": {
    "user_id": "DONOR-002",
    "name": "Pizza Palace",
    "email": "pizza@email.com",
    "role": "DONOR",
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

### POST /auth/login
Authenticate and receive JWT token.
```json
Request:
{
  "email": "pizza@email.com",
  "password": "securepass123"
}

Response (200):
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "user_id": "DONOR-002",
    "name": "Pizza Palace",
    "role": "DONOR"
  }
}
```

### GET /users/{user_id}
Get user profile (requires auth).
```json
Response (200):
{
  "user_id": "RESTAURANT-001",
  "name": "Green Kitchen Restaurant",
  "email": "greengitchen@email.com",
  "role": "DONOR",
  "phone": "+1-555-0101",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "created_at": "2025-01-10T08:00:00Z"
}
```

### PUT /users/{user_id}
Update user profile (requires auth).

### GET /users
List all users (admin only). Supports query params: role, page, limit.

### GET /health
Health check endpoint.
```json
Response (200):
{
  "status": "healthy",
  "service": "user-service",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

## 2. Donation Service (Port 8002)

### POST /donations
Create a new donation (requires DONOR auth).
```json
Request:
{
  "food_name": "Vegetable Curry",
  "food_type": "cooked_meal",
  "quantity": 25.0,
  "unit": "kg",
  "prepared_at": "2025-01-15T08:00:00Z",
  "expiry_time": "2025-01-16T08:00:00Z",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "image": <multipart file>
}

Response (201):
{
  "message": "Donation created successfully",
  "donation": {
    "donation_id": "DON-001",
    "food_name": "Vegetable Curry",
    "status": "AVAILABLE",
    "lamport_timestamp": 1,
    "vector_timestamp": {"SVC-DONATION": 1},
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

### GET /donations
List all donations. Supports filters: status, food_type, donor_id, page, limit.

### GET /donations/{donation_id}
Get donation details.

### PUT /donations/{donation_id}
Update donation details (owner only).

### DELETE /donations/{donation_id}
Cancel a donation (owner only, status must be AVAILABLE).

### GET /donations/available
List only AVAILABLE donations for matching.

### GET /events
List distributed events for this service.

### GET /health
Health check.

---

## 3. Matching Service (Port 8003)

### POST /matching/run
Trigger the matching algorithm (admin only).
```json
Response (200):
{
  "message": "Matching completed",
  "matches_found": 3,
  "matches": [
    {
      "donation_id": "DON-001",
      "requirement_id": "REQ-001",
      "ngo_id": "NGO-001",
      "match_score": 0.92,
      "food_type_match": true,
      "proximity_km": 4.5
    }
  ]
}
```

### GET /matching/auto-match
Trigger automatic matching based on incoming donations.

### GET /requirements
List all NGO requirements.

### POST /requirements
Create a new NGO requirement (requires NGO auth).
```json
Request:
{
  "food_type": "cooked_meal",
  "required_quantity": 50.0,
  "priority": 1
}
```

### GET /requirements/{requirement_id}
Get requirement details.

### DELETE /requirements/{requirement_id}
Delete a requirement (owner only).

### GET /leader-election/status
Check current leader service status.

### POST /leader-election/heartbeat
Send heartbeat to coordinator.

### GET /health
Health check.

---

## 4. Inventory Service (Port 8004)

### gRPC Endpoints (Port 50051)

#### CheckAvailability
```protobuf
rpc CheckAvailability(CheckRequest) returns (CheckResponse);
// CheckRequest: { donation_id: string }
// CheckResponse: { available: bool, quantity: float, status: string, lamport_timestamp: int32 }
```

#### ReserveDonation
```protobuf
rpc ReserveDonation(ReserveRequest) returns (ReserveResponse);
// ReserveRequest: { donation_id: string, ngo_id: string, lamport_timestamp: int32, vector_timestamp: map<string,int32> }
// ReserveResponse: { success: bool, message: string, new_lamport_timestamp: int32, new_vector_timestamp: map<string,int32> }
```

#### GetInventory
```protobuf
rpc GetInventory(InventoryRequest) returns (InventoryResponse);
// InventoryRequest: { food_type_filter: string, status_filter: string }
// InventoryResponse: { items: repeated InventoryItem, total_count: int32, total_quantity: float }
```

#### ReleaseDonation
```protobuf
rpc ReleaseDonation(ReleaseRequest) returns (ReleaseResponse);
// ReleaseRequest: { donation_id: string, reason: string, lamport_timestamp: int32, vector_timestamp: map<string,int32> }
// ReleaseResponse: { success: bool, message: string, new_lamport_timestamp: int32, new_vector_timestamp: map<string,int32> }
```

### REST Endpoints

### GET /inventory
List all inventory items. Query params: food_type, status.

### GET /inventory/{donation_id}
Check specific donation availability.

### POST /inventory/{donation_id}/reserve
Reserve a donation for an NGO.

### POST /inventory/{donation_id}/release
Release a reservation.

### GET /snapshot
Trigger Chandy-Lamport snapshot.

### GET /mutual-exclusion/status
Check mutex lock status.

### GET /health
Health check.

---

## 5. Delivery Service (Port 8005)

### POST /deliveries
Create a new delivery assignment (auto-assigned by matching).
```json
Request:
{
  "donation_id": "DON-001",
  "ngo_id": "NGO-001",
  "pickup_lat": 40.7128,
  "pickup_lng": -74.0060,
  "drop_lat": 40.7589,
  "drop_lng": -73.9851
}

Response (201):
{
  "delivery_id": "DEL-001",
  "status": "ASSIGNED",
  "volunteer_id": "VOL-001",
  "created_at": "2025-01-15T11:00:00Z"
}
```

### GET /deliveries
List deliveries. Query params: status, volunteer_id, ngo_id.

### GET /deliveries/{delivery_id}
Get delivery details.

### PUT /deliveries/{delivery_id}/status
Update delivery status (volunteer only).
```json
Request:
{
  "status": "PICKED_UP"
}
```

### PUT /deliveries/{delivery_id}/complete
Mark delivery as completed.

### GET /deliveries/active/{volunteer_id}
Get active deliveries for a volunteer.

### GET /health
Health check.

---

## 6. Notification Service (Port 8006)

### WebSocket: ws://localhost:8006/ws/{user_id}
Connect for real-time notifications.
```json
// Server sends:
{
  "type": "delivery_update",
  "title": "Delivery Update",
  "message": "Your delivery DEL-001 has been picked up",
  "timestamp": "2025-01-15T11:30:00Z"
}
```

### GET /notifications/{user_id}
Get all notifications for a user.

### PUT /notifications/{id}/read
Mark a notification as read.

### GET /health
Health check.

---

## 7. Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request / Validation Error |
| 401 | Unauthorized (invalid or missing token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource Not Found |
| 409 | Conflict (duplicate resource) |
| 500 | Internal Server Error |

---

## 8. Error Response Format
```json
{
  "error": "Error type",
  "message": "Detailed error description",
  "timestamp": "2025-01-15T10:30:00Z"
}
```
