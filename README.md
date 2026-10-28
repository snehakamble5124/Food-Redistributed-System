# Distributed Food Waste Redistribution System

A microservice-based distributed system that connects food donors (restaurants, catering services) with NGOs and volunteers to redistribute surplus food to those in need. Built with Python, FastAPI, gRPC, RabbitMQ, PostgreSQL, and WebSocket, implementing core distributed systems algorithms.

---

## Architecture Overview

The system consists of 6 microservices, each handling a specific domain:

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| User Service | 8001 | REST | Authentication, user management |
| Donation Service | 8002 | REST + RabbitMQ | Food donation CRUD, event publishing |
| Matching Service | 8003 | REST + RabbitMQ | Donor-NGO matching algorithm |
| Inventory Service | 8004 | REST + gRPC (50051) | Stock tracking, reservations |
| Delivery Service | 8005 | REST | Volunteer assignment, delivery tracking |
| Notification Service | 8006 | WebSocket + RabbitMQ | Real-time push notifications |

**Infrastructure**: PostgreSQL 15, RabbitMQ 3, Docker Compose, Nginx (frontend)

**Communication**: REST (client-facing), gRPC (internal high-performance), RabbitMQ (async events), WebSocket (real-time push)

---

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15 (if running manually)
- protoc (Protocol Buffer compiler, for gRPC)

---

## Setup Instructions

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd distributed-food-waste

# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Verify services are running
docker-compose -f docker/docker-compose.yml ps

# Check health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
curl http://localhost:8006/health
```

### Manual Setup

```bash
# 1. Set up PostgreSQL
psql -U postgres -c "CREATE DATABASE food_waste_db;"
psql -U postgres -d food_waste_db -f database/schema.sql
psql -U postgres -d food_waste_db -f database/seed.sql

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Generate gRPC code
cd grpc
python -m grpc_tools.protoc -I. --python_out=../generated --grpc_python_out=../generated donation.proto
cd ..

# 4. Set environment variables
export DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/food_waste_db
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/
export JWT_SECRET=your-secret-key

# 5. Start each service in a separate terminal
uvicorn services.user_service.main:app --port 8001
uvicorn services.donation_service.main:app --port 8002
uvicorn services.matching_service.main:app --port 8003
uvicorn services.inventory_service.main:app --port 8004
uvicorn services.delivery_service.main:app --port 8005
uvicorn services.notification_service.main:app --port 8006
```

---

## API Endpoints Summary

### User Service (8001)
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login, get JWT token
- `GET /users/{id}` - Get user profile
- `PUT /users/{id}` - Update profile

### Donation Service (8002)
- `POST /donations` - Create donation
- `GET /donations` - List donations (filtered)
- `GET /donations/available` - Available donations
- `GET /donations/{id}` - Donation details
- `DELETE /donations/{id}` - Cancel donation

### Matching Service (8003)
- `POST /matching/run` - Run matching algorithm
- `POST /requirements` - Create NGO requirement
- `GET /requirements` - List requirements

### Inventory Service (8004)
- `GET /inventory` - List inventory
- `GET /inventory/{id}` - Check availability
- `POST /inventory/{id}/reserve` - Reserve donation
- `POST /inventory/{id}/release` - Release reservation
- gRPC: `CheckAvailability`, `ReserveDonation`, `GetInventory`, `ReleaseDonation`

### Delivery Service (8005)
- `POST /deliveries` - Create delivery
- `GET /deliveries` - List deliveries
- `PUT /deliveries/{id}/status` - Update status
- `PUT /deliveries/{id}/complete` - Complete delivery

### Notification Service (8006)
- `WS /ws/{user_id}` - WebSocket for real-time notifications
- `GET /notifications/{user_id}` - Get notifications
- `PUT /notifications/{id}/read` - Mark as read

---

## Distributed Algorithms

### 1. Lamport Clock
Logical timestamps providing partial ordering of events across services. Each service increments its counter on local events and synchronizes on message exchange (max + 1).

### 2. Vector Clock
Vector timestamps tracking causal relationships. Each donation stores a JSONB vector mapping service IDs to counters, enabling detection of concurrent events.

### 3. Bully Election
Leader election for the Matching Service coordinator. When the coordinator fails, services with higher IDs are contacted. The highest responding service becomes the new leader.

### 4. Mutual Exclusion (Centralized)
The Inventory Service coordinator grants exclusive access for donation reservations. Only one service can reserve a donation at a time, preventing double-booking.

### 5. Chandy-Lamport Snapshot
Consistent global state capture using marker messages. The Inventory Service initiates snapshots, recording states across all services without stopping execution.

### 6. Wait-for Graph Deadlock Detection
Tracks inter-service dependencies. Cycles in the wait-for graph indicate deadlocks, resolved by aborting the youngest transaction.

---

## Testing Guide

See [docs/testing.md](docs/testing.md) for 10 comprehensive test scenarios:

1. User Registration and Authentication
2. Food Donation Creation and Management
3. NGO Requirement Creation and Matching
4. Inventory Reservation via gRPC
5. Delivery Assignment and Tracking
6. Real-Time Notifications via WebSocket
7. Lamport Clock Consistency
8. Vector Clock Causality Detection
9. Service Health and Heartbeat Monitoring
10. Chandy-Lamport Snapshot and Global State

---

## Project Structure

```
distributed-food-waste/
├── database/
│   ├── schema.sql          # PostgreSQL schema (7 tables)
│   └── seed.sql            # Sample data for development
├── grpc/
│   ├── donation.proto      # gRPC service definition
│   └── generated/
│       └── __init__.py     # Generated Python stubs
├── docker/
│   ├── Dockerfile          # Multi-stage Python Dockerfile
│   └── docker-compose.yml  # Full service orchestration
├── docs/
│   ├── architecture.md     # System architecture document
│   ├── api.md              # API documentation
│   ├── algorithms.md       # Distributed algorithms explained
│   └── testing.md          # Test scenarios guide
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## Technologies Used

| Category | Technology |
|----------|-----------|
| Language | Python 3.11 |
| Web Framework | FastAPI 0.104.1 |
| Database | PostgreSQL 15 |
| Message Broker | RabbitMQ 3 |
| RPC Framework | gRPC (grpcio 1.60.0) |
| Real-time | WebSocket (websockets 12.0) |
| Authentication | JWT (python-jose), bcrypt (passlib) |
| Containerization | Docker, Docker Compose |
| ORM | SQLAlchemy 2.0.23 |
| Server | Uvicorn 0.24.0 |

---

## License

MIT License
