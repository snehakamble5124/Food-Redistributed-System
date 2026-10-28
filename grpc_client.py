import os
import json
import urllib.request
from dataclasses import dataclass


class InventoryServiceClient:
    def __init__(self, host: str = "localhost", port: int = 8004):
        self.host = host
        self.port = port
        self.rest_base = f"http://{host}:{port}"
        self.grpc_available = False
        self.channel = None
        self.stub = None

    def check_availability(self, donation_id: str) -> dict:
        return self._rest_check_availability(donation_id)

    def reserve_donation(self, donation_id: str, ngo_id: str) -> dict:
        return self._rest_reserve_donation(donation_id, ngo_id)

    def get_inventory(self) -> list[dict]:
        return self._rest_get_inventory()

    def release_donation(self, donation_id: str) -> dict:
        return self._rest_release_donation(donation_id)

    def _rest_check_availability(self, donation_id: str) -> dict:
        try:
            url = f"{self.rest_base}/inventory/check/{donation_id}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {
                    "available": data.get("available", False),
                    "quantity": data.get("quantity", 0.0),
                    "message": data.get("message", "Checked via REST"),
                }
        except Exception as e:
            return {
                "available": False,
                "quantity": 0.0,
                "message": f"Service unavailable: {str(e)}",
            }

    def _rest_reserve_donation(self, donation_id: str, ngo_id: str) -> dict:
        try:
            url = f"{self.rest_base}/inventory/reserve"
            payload = json.dumps({"donation_id": donation_id, "ngo_id": ngo_id}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {
                    "success": data.get("success", False),
                    "message": data.get("message", "Reserved via REST"),
                }
        except Exception as e:
            return {"success": False, "message": f"Service unavailable: {str(e)}"}

    def _rest_get_inventory(self) -> list[dict]:
        try:
            url = f"{self.rest_base}/inventory/list"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return data.get("items", [])
        except Exception as e:
            return []

    def _rest_release_donation(self, donation_id: str) -> dict:
        try:
            url = f"{self.rest_base}/inventory/release/{donation_id}"
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {
                    "success": data.get("success", False),
                    "message": data.get("message", "Released via REST"),
                }
        except Exception as e:
            return {"success": False, "message": f"Service unavailable: {str(e)}"}
