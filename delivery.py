import math
from datetime import datetime
from sqlalchemy.orm import Session
from delivery_service.models import Delivery


class DeliveryManager:
    def __init__(self):
        self.active_deliveries: dict[str, dict] = {}
        self.volunteer_assignments: dict[str, list[str]] = {}

    def create_delivery(
        self,
        db: Session,
        donation_id: str,
        ngo_id: str,
        volunteer_id: str | None = None,
        pickup_lat: float | None = None,
        pickup_lng: float | None = None,
        pickup_address: str | None = None,
        drop_lat: float | None = None,
        drop_lng: float | None = None,
        drop_address: str | None = None,
    ) -> Delivery:
        import uuid
        delivery_id = f"DEL-{uuid.uuid4().hex[:8].upper()}"

        delivery = Delivery(
            delivery_id=delivery_id,
            donation_id=donation_id,
            ngo_id=ngo_id,
            volunteer_id=volunteer_id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            pickup_address=pickup_address,
            drop_lat=drop_lat,
            drop_lng=drop_lng,
            drop_address=drop_address,
            status="ASSIGNED",
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        self.active_deliveries[delivery_id] = {
            "delivery_id": delivery_id,
            "donation_id": donation_id,
            "ngo_id": ngo_id,
            "volunteer_id": volunteer_id,
            "status": "ASSIGNED",
            "created_at": datetime.utcnow().isoformat(),
        }

        if volunteer_id:
            if volunteer_id not in self.volunteer_assignments:
                self.volunteer_assignments[volunteer_id] = []
            self.volunteer_assignments[volunteer_id].append(delivery_id)

        return delivery

    def update_delivery_status(
        self,
        db: Session,
        delivery_id: str,
        new_status: str,
    ) -> Delivery:
        VALID_TRANSITIONS = {
            "ASSIGNED": ["PICKED_UP", "CANCELLED"],
            "PICKED_UP": ["IN_TRANSIT", "DELIVERED"],
            "IN_TRANSIT": ["DELIVERED"],
            "DELIVERED": [],
            "CANCELLED": [],
        }

        delivery = db.query(Delivery).filter(Delivery.delivery_id == delivery_id).first()
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")

        allowed = VALID_TRANSITIONS.get(delivery.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {delivery.status} to {new_status}. "
                f"Allowed: {allowed}"
            )

        delivery.status = new_status
        if new_status == "DELIVERED":
            delivery.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(delivery)

        if delivery_id in self.active_deliveries:
            self.active_deliveries[delivery_id]["status"] = new_status
            if new_status == "DELIVERED":
                self.active_deliveries[delivery_id]["completed_at"] = datetime.utcnow().isoformat()

        return delivery

    def get_volunteer_deliveries(self, db: Session, volunteer_id: str) -> list[Delivery]:
        return (
            db.query(Delivery)
            .filter(Delivery.volunteer_id == volunteer_id)
            .order_by(Delivery.created_at.desc())
            .all()
        )

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_delivery_eta(self, delivery_id: str, volunteer_lat: float, volunteer_lng: float) -> dict:
        delivery_info = self.active_deliveries.get(delivery_id)
        if not delivery_info:
            return {"error": "Delivery not found in active deliveries"}

        # Calculate distance to pickup or drop based on status
        status = delivery_info.get("status", "ASSIGNED")

        # Retrieve from DB to get coordinates
        from database import SessionLocal
        db = SessionLocal()
        try:
            delivery = db.query(Delivery).filter(Delivery.delivery_id == delivery_id).first()
            if not delivery:
                return {"error": "Delivery not found in database"}

            if status == "ASSIGNED":
                target_lat = delivery.pickup_lat
                target_lng = delivery.pickup_lng
            else:
                target_lat = delivery.drop_lat
                target_lng = delivery.drop_lng

            if not target_lat or not target_lng:
                return {"error": "Target coordinates not available"}

            distance = self.haversine_distance(volunteer_lat, volunteer_lng, target_lat, target_lng)
            avg_speed_kmh = 30.0
            eta_minutes = (distance / avg_speed_kmh) * 60

            return {
                "delivery_id": delivery_id,
                "distance_km": round(distance, 2),
                "eta_minutes": round(eta_minutes, 1),
                "target_lat": target_lat,
                "target_lng": target_lng,
            }
        finally:
            db.close()


delivery_manager = DeliveryManager()
