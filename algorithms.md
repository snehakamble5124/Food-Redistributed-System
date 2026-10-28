# Distributed Algorithms - Food Waste Redistribution System

## 1. Lamport Clock

### Concept
A Lamport Clock is a logical clock that assigns a monotonically increasing integer timestamp to events, establishing a partial ordering based on the happened-before relation.

### Rules
1. Before executing an event, increment the local counter.
2. When sending a message, attach the current counter value.
3. When receiving a message, set local counter = max(local, received) + 1.

### Implementation in This System
Each service (donation_service, matching_service, inventory_service, delivery_service) maintains its own Lamport counter. Every mutation to the database records the current Lamport timestamp in the `distributed_events` table and the `lamport_timestamp` column in `donations`.

### Example
```
Timeline:
  Donation Service          Inventory Service
  --------------------      --------------------
  L=0 (initial)
  Create DON-001
  L=1 -> sends message ----> Receives: L=max(0,1)+1=2
  Update status              Reserve DON-001
  L=2                        L=3 -> sends message ---->
  Receives: L=max(2,3)+1=4

Result: Events are ordered as L=1, L=2, L=3, L=4
```

### Code Logic
```python
def increment_lamport(self):
    self.lamport_timestamp += 1
    return self.lamport_timestamp

def receive_message(self, received_timestamp):
    self.lamport_timestamp = max(self.lamport_timestamp, received_timestamp) + 1
    return self.lamport_timestamp
```

---

## 2. Vector Clock

### Concept
A Vector Clock is an array of counters, one per process/service. It captures causal relationships between events and can detect concurrent events.

### Rules
1. Before a local event, increment own position in the vector.
2. On sending a message, attach the full vector.
3. On receiving a message, merge vectors element-wise: v[i] = max(local[i], received[i]) for all i, then increment own position.

### Implementation
Each donation carries a `vector_timestamp` JSONB field mapping service IDs to their counter values. This allows the system to determine if two events are causally related or concurrent.

### Example
```
Services: [donation, inventory, matching]

Donation Service creates DON-001:
  V = [1, 0, 0]

Inventory Service checks availability:
  V = [0, 1, 0]

Matching Service matches DON-001:
  Receives [1, 0, 0] from Donation
  Merges: [1, 0, 1] (max of each + increment own)
  Now: V = [1, 0, 1]

Detecting concurrency:
  Event A: V = [3, 1, 0] (donation service active)
  Event B: V = [1, 1, 2] (matching service active)
  Neither dominates -> Events are CONCURRENT
```

### Code Logic
```python
def increment_vector(self):
    self.vector_clock[self.service_id] += 1
    return self.vector_clock.copy()

def merge_vectors(self, received_vector):
    for service_id in received_vector:
        self.vector_clock[service_id] = max(
            self.vector_clock.get(service_id, 0),
            received_vector[service_id]
        )
    self.vector_clock[self.service_id] += 1
    return self.vector_clock.copy()

def are_concurrent(self, v1, v2):
    v1_dominates = all(v1.get(k, 0) >= v2.get(k, 0) for k in set(v1) | set(v2))
    v2_dominates = all(v2.get(k, 0) >= v1.get(k, 0) for k in set(v1) | set(v2))
    return not v1_dominates and not v2_dominates
```

---

## 3. Bully Election Algorithm

### Concept
The Bully Election algorithm is used to elect a coordinator (leader) in a distributed system. Any process can initiate an election. The process with the highest ID wins.

### Rules
1. If a process P detects the coordinator is down, it sends an ELECTION message to all processes with higher IDs.
2. If no higher process responds, P declares itself coordinator.
3. If a higher process responds, it takes over the election.
4. When a process starts or recovers, it initiates an election.

### Implementation
The Matching Service acts as the coordinator. If it stops sending heartbeats, other services detect this and trigger a Bully Election. Service IDs map to port numbers (higher port = higher priority).

### Example
```
Services: user(8001), donation(8002), matching(8003), inventory(8004), delivery(8005)

Coordinator (matching:8003) goes down.

Step 1: inventory(8004) detects missing heartbeat
        inventory sends ELECTION to delivery(8005) [higher ID]
Step 2: delivery(8005) responds "I am alive"
        delivery sends ELECTION to nobody [highest ID]
Step 3: delivery(8005) declares itself coordinator
        sends COORDINATOR message to all
Step 4: All services update leader to delivery(8005)
```

### Code Logic
```python
def initiate_election(self):
    higher_services = [
        s for s in self.known_services
        if s.port > self.port and s.status == "UP"
    ]
    if not higher_services:
        self.become_coordinator()
        return

    for service in higher_services:
        send_election_message(service)

    # Wait for response timeout
    if no_response_received():
        self.become_coordinator()

def become_coordinator(self):
    self.is_coordinator = True
    for service in self.known_services:
        send_coordinator_message(service)
```

---

## 4. Mutual Exclusion (Centralized Algorithm)

### Concept
Mutual exclusion ensures that only one process accesses a critical section at a time. The centralized approach uses a coordinator to grant permissions.

### Rules
1. Process wanting to enter critical section sends REQUEST to coordinator.
2. Coordinator grants permission if no other process is in the critical section.
3. Process enters critical section, does work, then sends RELEASE.
4. Coordinator queues requests if critical section is occupied.

### Implementation
The Inventory Service uses centralized mutual exclusion for donation reservation operations. Only one service can reserve a specific donation at a time to prevent double-booking.

### Example
```
Matching Service wants to reserve DON-001:
  -> Sends REQUEST to Inventory Coordinator
  -> Coordinator grants PERMISSION (no active lock)

Simultaneously, Delivery Service wants to update DON-001:
  -> Sends REQUEST to Inventory Coordinator
  -> Coordinator DEFERS (lock held by Matching)

Matching completes reservation:
  -> Sends RELEASE to Coordinator
  -> Coordinator grants PERMISSION to Delivery
```

### Code Logic
```python
class MutexCoordinator:
    def __init__(self):
        self.locked = False
        self.queue = []

    def request_lock(self, service_id, resource_id):
        if not self.locked:
            self.locked = True
            self.current_holder = service_id
            return "GRANTED"
        else:
            self.queue.append((service_id, resource_id))
            return "DEFERRED"

    def release_lock(self, service_id):
        if self.current_holder == service_id:
            self.locked = False
            if self.queue:
                next_service, _ = self.queue.pop(0)
                self.locked = True
                self.current_holder = next_service
                return "GRANTED_TO_NEXT"
        return "RELEASED"
```

---

## 5. Chandy-Lamport Snapshot

### Concept
The Chandy-Lamport algorithm captures a consistent global state of a distributed system without stopping execution. It uses marker messages on communication channels.

### Rules
1. Initiator records its local state and sends MARKER on all outgoing channels.
2. When a process receives a MARKER on a channel:
   - If it has not yet recorded its state, record state now and send MARKER on all other channels.
   - Mark the channel as "cut" (messages before marker = pre-snapshot, after = post-snapshot).
3. A process records the state of each incoming channel when it first receives a MARKER.

### Implementation
A periodic snapshot is triggered to capture the global state of all donations, deliveries, and service health. The Inventory Service acts as the coordinator for snapshots.

### Example
```
Services: Donation, Inventory, Matching

1. Inventory (coordinator) initiates snapshot:
   - Records own state: 5 reservations active
   - Sends MARKER to Donation and Matching

2. Donation receives MARKER from Inventory:
   - Records state: 12 donations available
   - Sends MARKER to Inventory and Matching
   - Marks Inventory channel as "cut"

3. Matching receives MARKER from Donation and Inventory:
   - Records state: 3 pending matches
   - Marks both channels as "cut"

4. Snapshot complete:
   Global State = {
     donation_service: {available: 12, reserved: 3, expired: 1},
     inventory_service: {reservations: 5, locks: 1},
     matching_service: {pending: 3, completed: 8}
   }
```

### Code Logic
```python
class SnapshotCoordinator:
    def initiate_snapshot(self):
        self.local_state = self.record_local_state()
        for channel in self.outgoing_channels:
            channel.send(MARKER, self.snapshot_id)
        self.markers_sent = True

    def on_receive_marker(self, channel, from_service):
        if not self.state_recorded:
            self.local_state = self.record_local_state()
            self.state_recorded = True
            for ch in self.outgoing_channels:
                if ch != channel:
                    ch.send(MARKER, self.snapshot_id)
        self.channel_states[channel] = "CUT"

    def record_local_state(self):
        return {
            "donations": self.get_donation_counts(),
            "reservations": self.get_active_reservations(),
            "timestamp": self.get_lamport_time()
        }
```

---

## 6. Wait-for Graph Deadlock Detection

### Concept
A Wait-for Graph (WFG) tracks which processes are waiting on which other processes. A cycle in the graph indicates a deadlock.

### Rules
1. When process A waits for process B, add edge A->B.
2. When the wait is resolved, remove edge A->B.
3. Periodically check for cycles using DFS.
4. If a cycle exists, abort the youngest transaction to break the deadlock.

### Implementation
The system tracks inter-service dependencies during reservation and delivery operations. If the Matching Service waits on Inventory Service, which waits on Donation Service, which waits on Matching Service, a deadlock is detected.

### Example
```
Wait-for Graph:
  Matching -> Inventory (waiting for reservation confirmation)
  Inventory -> Donation (waiting for status update)
  Donation -> Matching (waiting for match result)

Cycle detected: Matching -> Inventory -> Donation -> Matching

Resolution: Abort the youngest transaction (Donation service's update)
            Donate service releases its lock, breaking the cycle.
```

### Code Logic
```python
class WaitForGraph:
    def __init__(self):
        self.edges = {}  # service_id -> set of services it waits for

    def add_edge(self, waiter, waitee):
        if waiter not in self.edges:
            self.edges[waiter] = set()
        self.edges[waiter].add(waitee)

    def remove_edge(self, waiter, waitee):
        if waiter in self.edges:
            self.edges[waiter].discard(waitee)

    def detect_cycle(self):
        visited = set()
        rec_stack = set()

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.edges.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in self.edges:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def break_deadlock(self):
        if self.detect_cycle():
            youngest = self.find_youngest_transaction()
            youngest.abort()
            self.remove_edges_involving(youngest)
```

---

## Summary Table

| Algorithm | Purpose | Where Used |
|-----------|---------|------------|
| Lamport Clock | Partial event ordering | All services (donations table) |
| Vector Clock | Causal ordering + concurrency detection | Donations, events tables |
| Bully Election | Leader election | Matching Service coordination |
| Mutual Exclusion | Critical section protection | Inventory Service reservations |
| Chandy-Lamport Snapshot | Consistent global state capture | Inventory Service coordinator |
| Wait-for Graph | Deadlock detection | Inter-service dependency tracking |
