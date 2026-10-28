-- ============================================================
-- Distributed Food Waste Redistribution System
-- PostgreSQL Schema - Complete Database Design
-- ============================================================

-- Drop existing tables if they exist (for clean re-creation)
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS distributed_events CASCADE;
DROP TABLE IF EXISTS deliveries CASCADE;
DROP TABLE IF EXISTS ngo_requirements CASCADE;
DROP TABLE IF EXISTS donations CASCADE;
DROP TABLE IF EXISTS services_registry CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================================
-- 1. USERS TABLE
-- Stores all system users: Donors, NGOs, Volunteers, Admins
-- ============================================================
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('DONOR', 'NGO', 'VOLUNTEER', 'ADMIN')),
    phone VARCHAR(20),
    address VARCHAR(255),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_location ON users(latitude, longitude);

-- ============================================================
-- 2. DONATIONS TABLE
-- Tracks all food donations with distributed system fields
-- ============================================================
CREATE TABLE donations (
    donation_id VARCHAR(50) PRIMARY KEY,
    donor_id VARCHAR(50) NOT NULL,
    food_name VARCHAR(150) NOT NULL,
    food_type VARCHAR(50) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity > 0),
    unit VARCHAR(20) NOT NULL DEFAULT 'kg',
    prepared_at TIMESTAMP WITH TIME ZONE,
    expiry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    latitude DOUBLE PRECISION DEFAULT 0.0,
    longitude DOUBLE PRECISION DEFAULT 0.0,
    address VARCHAR(255),
    ngo_id VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
        CHECK (status IN ('AVAILABLE', 'RESERVED', 'IN_TRANSIT', 'DELIVERED', 'EXPIRED', 'CANCELLED')),
    lamport_timestamp INTEGER NOT NULL DEFAULT 0,
    vector_timestamp JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_donations_donor FOREIGN KEY (donor_id)
        REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_donations_donor ON donations(donor_id);
CREATE INDEX idx_donations_ngo ON donations(ngo_id);
CREATE INDEX idx_donations_status ON donations(status);
CREATE INDEX idx_donations_food_type ON donations(food_type);
CREATE INDEX idx_donations_expiry ON donations(expiry_time);
CREATE INDEX idx_donations_location ON donations(latitude, longitude);
CREATE INDEX idx_donations_lamport ON donations(lamport_timestamp);
CREATE INDEX idx_donations_available ON donations(status, expiry_time)
    WHERE status = 'AVAILABLE';

-- ============================================================
-- 3. NGO REQUIREMENTS TABLE
-- Stores food requirements from NGOs
-- ============================================================
CREATE TABLE ngo_requirements (
    requirement_id VARCHAR(50) PRIMARY KEY,
    ngo_id VARCHAR(50) NOT NULL,
    food_type VARCHAR(50) NOT NULL,
    required_quantity DOUBLE PRECISION NOT NULL CHECK (required_quantity > 0),
    priority INTEGER NOT NULL DEFAULT 1 CHECK (priority BETWEEN 1 AND 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_requirements_ngo FOREIGN KEY (ngo_id)
        REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_requirements_ngo ON ngo_requirements(ngo_id);
CREATE INDEX idx_requirements_food_type ON ngo_requirements(food_type);
CREATE INDEX idx_requirements_priority ON ngo_requirements(priority DESC);

-- ============================================================
-- 4. DELIVERIES TABLE
-- Tracks donation deliveries assigned to volunteers
-- ============================================================
CREATE TABLE deliveries (
    delivery_id VARCHAR(50) PRIMARY KEY,
    donation_id VARCHAR(50) NOT NULL,
    ngo_id VARCHAR(50) NOT NULL,
    volunteer_id VARCHAR(50),
    pickup_lat DOUBLE PRECISION NOT NULL,
    pickup_lng DOUBLE PRECISION NOT NULL,
    pickup_address VARCHAR(255),
    drop_lat DOUBLE PRECISION NOT NULL,
    drop_lng DOUBLE PRECISION NOT NULL,
    drop_address VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'ASSIGNED'
        CHECK (status IN ('ASSIGNED', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', 'FAILED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_deliveries_donation FOREIGN KEY (donation_id)
        REFERENCES donations(donation_id) ON DELETE CASCADE,
    CONSTRAINT fk_deliveries_ngo FOREIGN KEY (ngo_id)
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_deliveries_volunteer FOREIGN KEY (volunteer_id)
        REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_deliveries_donation ON deliveries(donation_id);
CREATE INDEX idx_deliveries_volunteer ON deliveries(volunteer_id);
CREATE INDEX idx_deliveries_ngo ON deliveries(ngo_id);
CREATE INDEX idx_deliveries_status ON deliveries(status);

-- ============================================================
-- 5. SERVICES REGISTRY TABLE
-- Microservice registry for service discovery and heartbeats
-- ============================================================
CREATE TABLE services_registry (
    service_id VARCHAR(50) PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    address VARCHAR(200) NOT NULL,
    port INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'UP'
        CHECK (status IN ('UP', 'DOWN', 'DEGRADED')),
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_services_status ON services_registry(status);
CREATE INDEX idx_services_name ON services_registry(service_name);

-- ============================================================
-- 6. DISTRIBUTED EVENTS TABLE
-- Event sourcing table for distributed system tracking
-- ============================================================
CREATE TABLE distributed_events (
    event_id SERIAL PRIMARY KEY,
    service_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    lamport_timestamp INTEGER NOT NULL DEFAULT 0,
    vector_timestamp JSONB DEFAULT '{}',
    event_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_events_service FOREIGN KEY (service_id)
        REFERENCES services_registry(service_id) ON DELETE CASCADE
);

CREATE INDEX idx_events_service ON distributed_events(service_id);
CREATE INDEX idx_events_type ON distributed_events(event_type);
CREATE INDEX idx_events_lamport ON distributed_events(lamport_timestamp);
CREATE INDEX idx_events_created ON distributed_events(created_at);

-- ============================================================
-- 7. DISTRIBUTED FILE SYSTEM - FILE METADATA (NameNode)
-- HDFS-style metadata: file -> chunk map stored as JSONB
-- ============================================================
CREATE TABLE dfs_files (
    file_id VARCHAR(50) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    chunk_size INTEGER NOT NULL DEFAULT 262144,
    num_chunks INTEGER NOT NULL DEFAULT 0,
    replication_factor INTEGER NOT NULL DEFAULT 2,
    chunks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_dfs_files_created ON dfs_files(created_at);

-- ============================================================
-- Grant permissions (for Docker PostgreSQL container)
-- ============================================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Blockchain ledger for donations/deliveries
CREATE TABLE IF NOT EXISTS blockchain_blocks (
    block_id SERIAL PRIMARY KEY,
    block_hash VARCHAR(64) NOT NULL UNIQUE,
    previous_hash VARCHAR(64),
    nonce BIGINT DEFAULT 0,
    data JSONB NOT NULL,
    tx_type VARCHAR(50),
    tx_id VARCHAR(50),
    merkle_root VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_blockchain_hash ON blockchain_blocks(block_hash);
CREATE INDEX IF NOT EXISTS idx_blockchain_prev ON blockchain_blocks(previous_hash);

-- Beacon protocol heartbeats
CREATE TABLE IF NOT EXISTS beacons (
    beacon_id VARCHAR(50) PRIMARY KEY,
    service_id VARCHAR(50) NOT NULL,
    node_id VARCHAR(50),
    location VARCHAR(255),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    rssi INTEGER DEFAULT -60,
    beacon_type VARCHAR(20) DEFAULT 'SERVICE',
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'ACTIVE'
);
CREATE INDEX IF NOT EXISTS idx_beacons_service ON beacons(service_id);
CREATE INDEX IF NOT EXISTS idx_beacons_last_seen ON beacons(last_seen);

