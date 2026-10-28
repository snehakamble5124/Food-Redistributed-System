import threading
import uuid
from collections import defaultdict


class LamportClock:
    def __init__(self):
        self._lock = threading.Lock()
        self._timestamp = 0

    def tick(self) -> int:
        with self._lock:
            self._timestamp += 1
            return self._timestamp

    def update(self, received_timestamp: int) -> int:
        with self._lock:
            self._timestamp = max(self._timestamp, received_timestamp) + 1
            return self._timestamp

    def get_timestamp(self) -> int:
        with self._lock:
            return self._timestamp


class MutexRequest:
    def __init__(self, node_id: str, timestamp: int, resource_id: str):
        self.node_id = node_id
        self.timestamp = timestamp
        self.resource_id = resource_id

    def __lt__(self, other):
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.node_id < other.node_id

    def __repr__(self):
        return f"MutexRequest(node={self.node_id}, t={self.timestamp}, res={self.resource_id})"


class MutualExclusion:
    def __init__(self, node_id: str | None = None):
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.clock = LamportClock()
        self._lock = threading.Lock()
        self._request_queue: dict[str, list[MutexRequest]] = defaultdict(list)
        self._lock_holders: dict[str, str] = {}
        self._reply_queues: dict[str, list[str]] = defaultdict(list)
        self._waiting: dict[str, threading.Event] = {}
        self._pending_replies: dict[str, set[str]] = {}
        self._all_nodes: set[str] = set()
        self._granted: dict[str, bool] = defaultdict(bool)

    def register_node(self, node_id: str):
        with self._lock:
            self._all_nodes.add(node_id)

    def request_critical_section(self, resource_id: str, timeout: float = 10.0) -> bool:
        timestamp = self.clock.tick()

        with self._lock:
            request = MutexRequest(self.node_id, timestamp, resource_id)
            self._request_queue[resource_id].append(request)
            self._request_queue[resource_id].sort()

            self._waiting[resource_id] = threading.Event()
            self._pending_replies[resource_id] = set(self._all_nodes - {self.node_id})
            self._granted[resource_id] = False

        print(f"[Mutex] Node {self.node_id} requesting CS for {resource_id} at t={timestamp}")

        # Simulate distributed mutex - in real system, this would send REQUEST messages
        # and wait for REPLIES from all other nodes.
        # For single-node simulation, grant immediately if we're the first in queue.
        with self._lock:
            queue = self._request_queue[resource_id]
            if queue and queue[0].node_id == self.node_id:
                self._lock_holders[resource_id] = self.node_id
                self._granted[resource_id] = True
                print(f"[Mutex] Node {self.node_id} acquired CS for {resource_id}")
                return True

        # Wait for grant
        acquired = self._waiting[resource_id].wait(timeout=timeout)

        with self._lock:
            if self._granted[resource_id]:
                self._lock_holders[resource_id] = self.node_id
                print(f"[Mutex] Node {self.node_id} acquired CS for {resource_id}")
                return True

        print(f"[Mutex] Node {self.node_id} failed to acquire CS for {resource_id}")
        return False

    def release_critical_section(self, resource_id: str):
        timestamp = self.clock.tick()
        with self._lock:
            self._request_queue[resource_id] = [
                r for r in self._request_queue[resource_id]
                if r.node_id != self.node_id
            ]
            self._lock_holders.pop(resource_id, None)
            self._pending_replies.pop(resource_id, None)
            self._waiting.pop(resource_id, None)
            self._granted[resource_id] = False

            # Grant to next in queue if any
            if self._request_queue[resource_id]:
                next_request = self._request_queue[resource_id][0]
                self._granted[resource_id] = True
                if resource_id in self._waiting:
                    self._waiting[resource_id].set()

        print(f"[Mutex] Node {self.node_id} released CS for {resource_id} at t={timestamp}")

    def receive_request(self, node_id: str, timestamp: int, resource_id: str) -> bool:
        self.clock.update(timestamp)

        with self._lock:
            request = MutexRequest(node_id, timestamp, resource_id)
            self._request_queue[resource_id].append(request)
            self._request_queue[resource_id].sort()

            my_request = None
            for r in self._request_queue[resource_id]:
                if r.node_id == self.node_id:
                    my_request = r
                    break

            # Reply immediately if we don't hold or want the lock,
            # or if our request has higher priority (lower timestamp)
            if my_request is None or my_request < request:
                print(f"[Mutex] Granting reply to node {node_id} for {resource_id}")
                return True
            else:
                print(f"[Mutex] Deferring reply to node {node_id} for {resource_id}")
                return False

    def receive_release(self, resource_id: str, node_id: str):
        self.clock.tick()
        with self._lock:
            self._request_queue[resource_id] = [
                r for r in self._request_queue[resource_id]
                if r.node_id != node_id
            ]
            if resource_id in self._pending_replies and node_id in self._pending_replies[resource_id]:
                self._pending_replies[resource_id].discard(node_id)
                if not self._pending_replies[resource_id] and resource_id in self._waiting:
                    self._granted[resource_id] = True
                    self._waiting[resource_id].set()

        print(f"[Mutex] Node {node_id} released for {resource_id}")

    def get_state(self, resource_id: str) -> dict:
        with self._lock:
            return {
                "resource_id": resource_id,
                "holder": self._lock_holders.get(resource_id, None),
                "queue_length": len(self._request_queue.get(resource_id, [])),
                "queue": [
                    {"node_id": r.node_id, "timestamp": r.timestamp}
                    for r in self._request_queue.get(resource_id, [])
                ],
                "current_timestamp": self.clock.get_timestamp(),
                "node_id": self.node_id,
            }

    def is_locked(self, resource_id: str) -> bool:
        with self._lock:
            return resource_id in self._lock_holders

    def get_holder(self, resource_id: str) -> str | None:
        with self._lock:
            return self._lock_holders.get(resource_id)
