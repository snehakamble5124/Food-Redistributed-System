import threading
from datetime import datetime


class InventoryManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._donations: dict[str, dict] = {}
        self._reservation_locks: dict[str, threading.Lock] = {}
        self._reserved_by: dict[str, str] = {}

    def _get_donation_lock(self, donation_id: str) -> threading.Lock:
        with self._lock:
            if donation_id not in self._reservation_locks:
                self._reservation_locks[donation_id] = threading.Lock()
            return self._reservation_locks[donation_id]

    def register_donation(self, donation_id: str, quantity: float, food_type: str = "", status: str = "AVAILABLE"):
        with self._lock:
            self._donations[donation_id] = {
                "donation_id": donation_id,
                "quantity": quantity,
                "food_type": food_type,
                "status": status,
                "reserved_by": None,
                "registered_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

    def check_availability(self, donation_id: str) -> dict:
        with self._lock:
            donation = self._donations.get(donation_id)
            if not donation:
                return {
                    "available": False,
                    "quantity": 0.0,
                    "message": f"Donation {donation_id} not found in inventory",
                    "status": None,
                }
            return {
                "available": donation["status"] == "AVAILABLE",
                "quantity": donation["quantity"],
                "message": "Available" if donation["status"] == "AVAILABLE" else f"Status: {donation['status']}",
                "status": donation["status"],
            }

    def reserve_donation(self, donation_id: str, ngo_id: str) -> dict:
        donation_lock = self._get_donation_lock(donation_id)
        with donation_lock:
            with self._lock:
                donation = self._donations.get(donation_id)
                if not donation:
                    return {"success": False, "message": f"Donation {donation_id} not found"}
                if donation["status"] != "AVAILABLE":
                    return {"success": False, "message": f"Donation is {donation['status']}, not AVAILABLE"}
                donation["status"] = "RESERVED"
                donation["reserved_by"] = ngo_id
                donation["updated_at"] = datetime.utcnow().isoformat()
                self._reserved_by[donation_id] = ngo_id
            return {
                "success": True,
                "message": f"Donation {donation_id} reserved by NGO {ngo_id}",
            }

    def release_donation(self, donation_id: str) -> dict:
        donation_lock = self._get_donation_lock(donation_id)
        with donation_lock:
            with self._lock:
                donation = self._donations.get(donation_id)
                if not donation:
                    return {"success": False, "message": f"Donation {donation_id} not found"}
                if donation["status"] != "RESERVED":
                    return {"success": False, "message": f"Donation is {donation['status']}, cannot release"}
                donation["status"] = "AVAILABLE"
                donation["reserved_by"] = None
                donation["updated_at"] = datetime.utcnow().isoformat()
                self._reserved_by.pop(donation_id, None)
            return {"success": True, "message": f"Donation {donation_id} released back to available"}

    def update_donation_status(self, donation_id: str, status: str) -> dict:
        with self._lock:
            donation = self._donations.get(donation_id)
            if not donation:
                return {"success": False, "message": f"Donation {donation_id} not found"}
            old_status = donation["status"]
            donation["status"] = status
            donation["updated_at"] = datetime.utcnow().isoformat()
            if status == "DELIVERED" or status == "CANCELLED":
                donation["reserved_by"] = None
                self._reserved_by.pop(donation_id, None)
        return {
            "success": True,
            "message": f"Donation {donation_id} status updated from {old_status} to {status}",
        }

    def get_inventory(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "donation_id": d["donation_id"],
                    "quantity": d["quantity"],
                    "food_type": d["food_type"],
                    "status": d["status"],
                    "reserved_by": d["reserved_by"],
                    "updated_at": d["updated_at"],
                }
                for d in self._donations.values()
            ]

    def get_available_count(self) -> int:
        with self._lock:
            return sum(1 for d in self._donations.values() if d["status"] == "AVAILABLE")

    def get_reserved_count(self) -> int:
        with self._lock:
            return sum(1 for d in self._donations.values() if d["status"] == "RESERVED")

    def remove_donation(self, donation_id: str) -> dict:
        with self._lock:
            if donation_id not in self._donations:
                return {"success": False, "message": f"Donation {donation_id} not found"}
            del self._donations[donation_id]
            self._reservation_locks.pop(donation_id, None)
            self._reserved_by.pop(donation_id, None)
        return {"success": True, "message": f"Donation {donation_id} removed from inventory"}


inventory_manager = InventoryManager()
