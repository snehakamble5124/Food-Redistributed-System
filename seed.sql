-- ============================================================
-- Distributed Food Waste Redistribution System
-- Seed Data - Initial Data for Development and Testing
-- ============================================================

-- Password hash for "password123" generated with bcrypt
-- $2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy

-- ============================================================
-- 1. USERS (Donor, NGOs, Volunteer, Admin)
-- ============================================================
INSERT INTO users (user_id, name, email, password_hash, role, phone, address, latitude, longitude) VALUES
('RESTAURANT-001', 'Green Kitchen Restaurant', 'greengitchen@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'DONOR', '+1-555-0101', '124 Green Street, New York, NY', 40.7128, -74.0060),

('NGO-001', 'Food For All Foundation', 'contact@foodforall.org',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'NGO', '+1-555-0202', '88 Relief Lane, Manhattan, NY', 40.7589, -73.9851),

('NGO-002', 'Feed the Hungry', 'feedhungry@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'NGO', '+1-555-0210', '45 Hunger-Free Road, Delhi', 28.62, 77.215),

('NGO-003', 'Food Bank Initiative', 'foodbank@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'NGO', '+1-555-0211', '101 Community Ave, Delhi', 28.63, 77.22),

('NGO-004', 'Community Kitchen', 'communitykitchen@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'NGO', '+1-555-0212', '230 Serve Drive, Delhi', 28.605, 77.195),

('NGO-005', 'Zero Waste Alliance', 'zerowaste@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'NGO', '+1-555-0213', '77 Green Way, Delhi', 28.64, 77.23),

('VOL-001', 'John Volunteer', 'john.volunteer@email.com',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'VOLUNTEER', '+1-555-0303', '12 Volunteer Lane, Delhi', 28.615, 77.21),

('ADMIN-001', 'System Administrator', 'admin@foodwaste.org',
 '$2b$12$7owNoIAdiJYU3SawjAbKqeXKKR./En4gxOxSjSJfs0NkepJSypajy',
 'ADMIN', '+1-555-0404', 40.7128, -74.0060);

-- ============================================================
-- 2. SERVICES REGISTRY (6 microservices)
-- ============================================================
INSERT INTO services_registry (service_id, service_name, address, port, status, last_heartbeat) VALUES
('SVC-USER', 'user_service', 'http://localhost', 8001, 'UP', NOW()),
('SVC-DONATION', 'donation_service', 'http://localhost', 8002, 'UP', NOW()),
('SVC-MATCHING', 'matching_service', 'http://localhost', 8003, 'UP', NOW()),
('SVC-INVENTORY', 'inventory_service', 'http://localhost', 8004, 'UP', NOW()),
('SVC-DELIVERY', 'delivery_service', 'http://localhost', 8005, 'UP', NOW());

-- ============================================================
-- 3. DONATIONS (3 donations with different statuses)
-- ============================================================
INSERT INTO donations (donation_id, donor_id, food_name, food_type, quantity, unit, prepared_at, expiry_time, latitude, longitude, address, status, lamport_timestamp, vector_timestamp) VALUES
('DON-001', 'RESTAURANT-001', 'Vegetable Curry', 'cooked_meal',
 25.0, 'kg', NOW() - INTERVAL '2 hours', NOW() + INTERVAL '22 hours',
 40.7128, -74.0060, '124 Green Street, New York, NY', 'AVAILABLE',
 5, '{"SVC-DONATION": 5, "SVC-USER": 2}'),

('DON-002', 'RESTAURANT-001', 'Fresh Bread Loaves', 'bakery',
 15.0, 'kg', NOW() - INTERVAL '1 hour', NOW() + INTERVAL '47 hours',
 40.7135, -74.0045, '125 Green Street, New York, NY', 'RESERVED',
 8, '{"SVC-DONATION": 8, "SVC-INVENTORY": 3}'),

('DON-003', 'RESTAURANT-001', 'Pasta Salad', 'cooked_meal',
 10.0, 'kg', NOW() - INTERVAL '5 hours', NOW() + INTERVAL '1 hour',
 40.7140, -74.0070, '130 Green Street, New York, NY', 'AVAILABLE',
 12, '{"SVC-DONATION": 12, "SVC-INVENTORY": 6}');

-- ============================================================
-- 4. NGO REQUIREMENTS (2 requirements)
-- ============================================================
INSERT INTO ngo_requirements (requirement_id, ngo_id, food_type, required_quantity, priority) VALUES
('REQ-001', 'NGO-001', 'cooked_meal', 50.0, 1),

('REQ-002', 'NGO-001', 'bakery', 30.0, 2);

-- ============================================================
-- 5. DELIVERIES (1 active delivery)
-- ============================================================
INSERT INTO deliveries (delivery_id, donation_id, ngo_id, volunteer_id, pickup_lat, pickup_lng, pickup_address, drop_lat, drop_lng, drop_address, status) VALUES
('DEL-001', 'DON-002', 'NGO-001', 'VOL-001',
 40.7135, -74.0045, '125 Green Street, New York, NY', 40.7589, -73.9851, '88 Relief Lane, Manhattan, NY', 'ASSIGNED');

-- ============================================================
-- 6. DISTRIBUTED EVENTS (Sample events with Lamport & Vector clocks)
-- ============================================================
INSERT INTO distributed_events (service_id, event_type, lamport_timestamp, vector_timestamp, event_data) VALUES
('SVC-DONATION', 'DONATION_CREATED', 1, '{"SVC-DONATION": 1}',
 '{"donation_id": "DON-001", "donor_id": "RESTAURANT-001", "food_name": "Vegetable Curry"}'),

('SVC-DONATION', 'DONATION_CREATED', 2, '{"SVC-DONATION": 2}',
 '{"donation_id": "DON-002", "donor_id": "RESTAURANT-001", "food_name": "Fresh Bread Loaves"}'),

('SVC-INVENTORY', 'STOCK_CHECKED', 3, '{"SVC-INVENTORY": 1, "SVC-DONATION": 2}',
 '{"donation_id": "DON-001", "available": true, "quantity": 25.0}'),

('SVC-MATCHING', 'MATCH_FOUND', 4, '{"SVC-MATCHING": 1, "SVC-DONATION": 2, "SVC-INVENTORY": 1}',
 '{"donation_id": "DON-002", "ngo_id": "NGO-001", "match_score": 0.95}'),

('SVC-INVENTORY', 'RESERVATION_MADE', 5, '{"SVC-INVENTORY": 2, "SVC-DONATION": 2, "SVC-MATCHING": 1}',
 '{"donation_id": "DON-002", "ngo_id": "NGO-001", "reserved_quantity": 15.0}'),

('SVC-DONATION', 'STATUS_UPDATED', 6, '{"SVC-DONATION": 6, "SVC-INVENTORY": 2, "SVC-MATCHING": 1}',
 '{"donation_id": "DON-002", "old_status": "AVAILABLE", "new_status": "RESERVED"}'),

('SVC-DELIVERY', 'DELIVERY_ASSIGNED', 7, '{"SVC-DELIVERY": 1, "SVC-DONATION": 6}',
 '{"delivery_id": "DEL-001", "volunteer_id": "VOL-001", "donation_id": "DON-002"}'),

('SVC-DONATION', 'DONATION_CREATED', 8, '{"SVC-DONATION": 8, "SVC-INVENTORY": 2}',
 '{"donation_id": "DON-003", "donor_id": "RESTAURANT-001", "food_name": "Pasta Salad"}'),

('SVC-INVENTORY', 'INVENTORY_UPDATED', 10, '{"SVC-INVENTORY": 4, "SVC-DONATION": 8}',
 '{"total_available_items": 2, "total_quantity_kg": 35.0}');

