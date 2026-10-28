# Architecture Document - Distributed Food Waste Redistribution System

## 1. Microservice Architecture Overview

The system follows a microservice architecture where each domain concern is handled by an independent, loosely-coupled service. Services communicate via REST APIs (synchronous), gRPC (high-performance internal), RabbitMQ (asynchronous messaging), and WebSockets (real-time push).

Six microservices share a PostgreSQL database and use RabbitMQ as a message broker. Each service maintains its own Lamport and Vector clocks for distributed event ordering.

---

## 2. Service Descriptions

### 2.1 User Service (Port 8001)
- **Responsibility**: User registration, authentication, profile management
- **Protocol**: REST API
- **Tables**: users
- **Features**: JWT auth, role-based access (DONOR/NGO/VOLUNTEER/ADMIN), bcrypt passwords, geolocation

### 2.2 Donation Service (Port 8002)
- **Responsibility**: Food donation CRUD, status management
- **Protocol**: REST API + RabbitMQ producer
- **Tables**: donations, distributed_events
- **Features**: CRUD operations, Lamport/Vector clock tracking, event publishing

### 2.3 Matching Service (Port 8003)
- **Responsibility**: Match donations to NGO requirements based on proximity and food type
- **Protocol**: REST API + RabbitMQ consumer/producer
- **Tables**: ngo_requirements, distributed_events
- **Features**: Proximity-based matching, food type filtering, priority scoring, Bully election for leader

### 2.4 Inventory Service (Port 8004 / gRPC 50051)
- **Responsibility**: Track donation availability, handle reservations
- **Protocol**: REST API + gRPC server
- **Tables**: donations (reads), distributed_events
- **Features**: gRPC for inter-service queries, availability checks, reservation management, mutual exclusion

### 2.5 Delivery Service (Port 8005)
- **Responsibility**: Assign volunteers, track delivery status
- **Protocol**: REST API
- **Tables**: deliveries, distributed_events
- **Features**: Volunteer assignment, delivery tracking, status updates

### 2.6 Notification Service (Port 8006)
- **Responsibility**: Send real-time notifications via WebSocket and store in DB
- **Protocol**: RabbitMQ consumer + WebSocket server
- **Tables**: notifications
- **Features**: WebSocket push to connected clients, email notification stubs, notification persistence

---

## 3. Communication Patterns

### 3.1 REST API (Synchronous)
Used for client-facing operations requiring immediate responses:
- User login/register -> User Service
- Create donation -> Donation Service
- Get matching results -> Matching Service
- Assign delivery -> Delivery Service

### 3.2 gRPC (High-Performance Internal)
Used for service-to-service calls requiring low latency:
- Donation Service queries Inventory Service for availability
- Matching Service checks stock via gRPC before confirming a match
- Inventory Service exposes CheckAvailability, ReserveDonation, GetInventory, ReleaseDonation RPCs

### 3.3 RabbitMQ (Asynchronous)
Used for decoupled event-driven communication:
- **Donation Events**: When a donation is created/updated, the Donation Service publishes to `donation.events`
- **Matching Events**: Matching Service consumes donation events, produces match results to `matching.results`
- **Notification Events**: All services publish notification requests to `notifications.queue`
- **Inventory Events**: Stock updates published to `inventory.updates`

### 3.4 WebSocket (Real-Time Push)
Used for live updates to connected frontend clients:
- Delivery status updates pushed to NGO and Volunteer dashboards
- New donation alerts pushed to matching NGOs
- Notification delivery to user browsers

---

## 4. Data Flow Diagrams

### 4.1 Donation Creation Flow
```
Donor -> [REST] -> Donation Service -> [DB Write] -> PostgreSQL
                -> [RabbitMQ Publish] -> matching.events queue
                -> [Lamport Increment] -> distributed_events table
                -> [Vector Clock Update] -> donations.vector_timestamp
```

### 4.2 Matching Flow
```
Matching Service <- [RabbitMQ Consume] <- donation.events
Matching Service -> [gRPC] -> Inventory Service -> CheckAvailability
Matching Service -> [DB Query] -> ngo_requirements
Matching Service -> [Algorithm] -> Proximity + Food Type Matching
Matching Service -> [DB Write] -> Creates match record
Matching Service -> [RabbitMQ Publish] -> matching.results
Matching Service -> [RabbitMQ Publish] -> notifications.queue
```

### 4.3 Delivery Flow
```
Matching Result -> [RabbitMQ] -> Delivery Service
Delivery Service -> [DB Write] -> deliveries table (ASSIGNED)
Delivery Service -> [WebSocket] -> Volunteer dashboard (new assignment)
Volunteer Accepts -> [REST] -> Delivery Service -> Status: PICKED_UP
Volunteer Delivers -> [REST] -> Delivery Service -> Status: DELIVERED
Delivery Service -> [RabbitMQ] -> notifications.queue (completion)
```

### 4.4 Notification Flow
```
Any Service -> [RabbitMQ Publish] -> notifications.queue
Notification Service <- [RabbitMQ Consume] <- notifications.queue
Notification Service -> [DB Write] -> notifications table
Notification Service -> [WebSocket Push] -> Connected user client
```

---

## 5. Distributed Systems Concepts

### 5.1 Lamport Clocks
Each service maintains a logical Lamport counter. On local events, the counter increments. On receiving messages, the counter takes max(local, received) + 1. This provides happens-before ordering across services.

### 5.2 Vector Clocks
Each donation carries a vector timestamp mapping service_id to counter. This detects causality and concurrent events. Two events are causally related if one vector dominates the other; otherwise they are concurrent.

### 5.3 Bully Election
When the leader service (Matching Service coordinator) goes down, remaining services detect missed heartbeats and initiate a Bully Election. The service with the highest ID wins and becomes the new coordinator.

### 5.4 Mutual Exclusion
The Inventory Service uses a centralized mutual exclusion server for reservation operations. Before modifying a donation reservation, a service must acquire a lock via the coordinator, ensuring consistency.

### 5.5 Chandy-Lamport Snapshot
Periodically, a coordinator initiates a global snapshot across all services. Each service records its local state and forwards marker messages along communication channels. This captures a consistent global state for auditing.

### 5.6 Deadlock Detection (Wait-for Graph)
The system maintains a wait-for graph tracking which services are waiting on responses from others. Cycles in this graph indicate deadlocks, which are resolved by aborting the youngest transaction.

---

## 6. Database Design

All services share a single PostgreSQL database (shared-nothing at the service level, shared database for simplicity). Tables are logically partitioned by service ownership:

| Table | Owner Service | Description |
|-------|--------------|-------------|
| users | User Service | All user accounts |
| donations | Donation Service | Food donations |
| ngo_requirements | Matching Service | NGO food needs |
| deliveries | Delivery Service | Delivery tracking |
| distributed_events | All Services | Event sourcing log |
| services_registry | All Services | Service discovery |
| notifications | Notification Service | User notifications |

---

## 7. Deployment Architecture

```
Internet -> [Reverse Proxy / Direct] -> [Services in Docker]
                 \-> [PostgreSQL]
                 \-> [RabbitMQ]
                 \-> [Frontend on Port 3000]
```
