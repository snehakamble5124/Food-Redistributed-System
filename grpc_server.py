import json
import threading
from concurrent import futures
from inventory_service.inventory import inventory_manager
from inventory_service.mutual_exclusion import enter_donation_critical_section, exit_donation_critical_section

try:
    import grpc
    from grpc import StatusCode
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


class InventoryServiceServicer:
    def __init__(self):
        self.manager = inventory_manager

    def CheckDonationAvailability(self, request, context):
        donation_id = request.donation_id if hasattr(request, 'donation_id') else request.get('donation_id', '')
        result = self.manager.check_availability(donation_id)
        if GRPC_AVAILABLE and context:
            return CheckAvailabilityResponse(
                available=result["available"],
                quantity=result["quantity"],
                message=result["message"],
            )
        return result

    def ReserveDonation(self, request, context):
        donation_id = request.donation_id if hasattr(request, 'donation_id') else request.get('donation_id', '')
        ngo_id = request.ngo_id if hasattr(request, 'ngo_id') else request.get('ngo_id', '')

        acquired = enter_donation_critical_section(donation_id, timeout=10.0)
        if not acquired:
            result = {"success": False, "message": "Could not acquire lock for reservation"}
        else:
            try:
                result = self.manager.reserve_donation(donation_id, ngo_id)
            finally:
                exit_donation_critical_section(donation_id)

        if GRPC_AVAILABLE and context:
            return ReserveDonationResponse(
                success=result["success"],
                message=result["message"],
            )
        return result

    def GetInventory(self, request, context):
        items = self.manager.get_inventory()
        if GRPC_AVAILABLE and context:
            return InventoryListResponse(
                items=[
                    InventoryDonationItem(
                        donation_id=i["donation_id"],
                        status=i["status"],
                        quantity=i["quantity"],
                    )
                    for i in items
                ]
            )
        return {"items": items}

    def ReleaseDonation(self, request, context):
        donation_id = request.donation_id if hasattr(request, 'donation_id') else request.get('donation_id', '')
        acquired = enter_donation_critical_section(donation_id, timeout=10.0)
        if not acquired:
            result = {"success": False, "message": "Could not acquire lock for release"}
        else:
            try:
                result = self.manager.release_donation(donation_id)
            finally:
                exit_donation_critical_section(donation_id)

        if GRPC_AVAILABLE and context:
            return ReleaseDonationResponse(
                success=result["success"],
                message=result["message"],
            )
        return result


class CheckAvailabilityRequest:
    def __init__(self, donation_id: str):
        self.donation_id = donation_id


class ReserveDonationRequest:
    def __init__(self, donation_id: str, ngo_id: str):
        self.donation_id = donation_id
        self.ngo_id = ngo_id


class ReleaseDonationRequest:
    def __init__(self, donation_id: str):
        self.donation_id = donation_id


class CheckAvailabilityResponse:
    def __init__(self, available: bool, quantity: float, message: str = ""):
        self.available = available
        self.quantity = quantity
        self.message = message


class ReserveDonationResponse:
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


class ReleaseDonationResponse:
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


class InventoryDonationItem:
    def __init__(self, donation_id: str, status: str, quantity: float):
        self.donation_id = donation_id
        self.status = status
        self.quantity = quantity


class InventoryListResponse:
    def __init__(self, items: list[InventoryDonationItem]):
        self.items = items


def start_grpc_server(host: str = "0.0.0.0", port: int = 50051):
    if not GRPC_AVAILABLE:
        print("gRPC not available, starting HTTP fallback server on gRPC port")
        start_http_fallback(host, port)
        return

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = InventoryServiceServicer()

    # In production, you would add the generated gRPC service to the server
    # inventory_pb2_grpc.add_InventoryServiceServicer_to_server(servicer, server)
    # For now, start an HTTP fallback
    print(f"gRPC library available. Starting HTTP fallback on {host}:{port}")
    start_http_fallback(host, port)


def start_http_fallback(host: str = "0.0.0.0", port: int = 50051):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    servicer = InventoryServiceServicer()

    class InventoryHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/inventory/check/"):
                donation_id = self.path.split("/")[-1]
                result = servicer.CheckDonationAvailability(
                    CheckAvailabilityRequest(donation_id), None
                )
                self._send_json(result)
            elif self.path == "/inventory/list":
                items = inventory_manager.get_inventory()
                self._send_json({"items": items})
            elif self.path.startswith("/inventory/state/"):
                donation_id = self.path.split("/")[-1]
                from inventory_service.mutual_exclusion import donation_mutex
                state = donation_mutex.get_state(donation_id)
                self._send_json(state)
            else:
                self._send_json({"error": "Not found"}, 404)

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

            if self.path == "/inventory/reserve":
                result = servicer.ReserveDonation(body, None)
                self._send_json(result)
            elif self.path.startswith("/inventory/release/"):
                donation_id = self.path.split("/")[-1]
                result = servicer.ReleaseDonation(
                    ReleaseDonationRequest(donation_id), None
                )
                self._send_json(result)
            elif self.path == "/inventory/register":
                donation_id = body.get("donation_id", "")
                quantity = body.get("quantity", 0.0)
                food_type = body.get("food_type", "")
                inventory_manager.register_donation(donation_id, quantity, food_type)
                self._send_json({"success": True, "message": f"Donation {donation_id} registered"})
            elif self.path == "/inventory/update-status":
                donation_id = body.get("donation_id", "")
                status = body.get("status", "")
                result = inventory_manager.update_donation_status(donation_id, status)
                self._send_json(result)
            else:
                self._send_json({"error": "Not found"}, 404)

        def _send_json(self, data, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, format, *args):
            pass

    server = HTTPServer((host, port), InventoryHTTPHandler)
    print(f"Inventory HTTP fallback server running on {host}:{port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
