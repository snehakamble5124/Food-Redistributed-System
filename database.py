import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres%40123@localhost:5432/food_waste",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    ensure_supporting_schema()


def ensure_supporting_schema():
    """Apply the small compatibility changes needed by all local services."""
    services = (
        ("SVC-USER", "user_service", 8001),
        ("SVC-DONATION", "donation_service", 8002),
        ("SVC-MATCHING", "matching_service", 8003),
        ("SVC-INVENTORY", "inventory_service", 8004),
        ("SVC-DELIVERY", "delivery_service", 8005),
    )

    with engine.begin() as connection:
        # Existing local databases predate NGO ownership of a reservation.
        connection.execute(text(
            "ALTER TABLE donations ADD COLUMN IF NOT EXISTS ngo_id VARCHAR(50)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_donations_ngo ON donations(ngo_id)"
        ))
        connection.execute(text(
            "ALTER TABLE donations ADD COLUMN IF NOT EXISTS address VARCHAR(255)"
        ))
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255)"
        ))
        connection.execute(text(
            "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS pickup_address VARCHAR(255)"
        ))
        connection.execute(text(
            "ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS drop_address VARCHAR(255)"
        ))

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS services_registry (
                service_id VARCHAR(50) PRIMARY KEY,
                service_name VARCHAR(100) NOT NULL,
                address VARCHAR(200) NOT NULL,
                port INTEGER NOT NULL,
                status VARCHAR(10) NOT NULL DEFAULT 'UP',
                last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS distributed_events (
                event_id SERIAL PRIMARY KEY,
                service_id VARCHAR(50) NOT NULL,
                event_type VARCHAR(100) NOT NULL,
                lamport_timestamp INTEGER NOT NULL DEFAULT 0,
                vector_timestamp JSONB DEFAULT '{}',
                event_data JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS dfs_files (
                file_id VARCHAR(50) PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                description VARCHAR(255) DEFAULT '',
                size_bytes BIGINT NOT NULL DEFAULT 0,
                chunk_size INTEGER NOT NULL DEFAULT 262144,
                num_chunks INTEGER NOT NULL DEFAULT 0,
                replication_factor INTEGER NOT NULL DEFAULT 2,
                chunks_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        for service_id, service_name, port in services:
            connection.execute(text("""
                INSERT INTO services_registry
                    (service_id, service_name, address, port, status, last_heartbeat)
                VALUES (:service_id, :service_name, 'http://localhost', :port, 'UP', NOW())
                ON CONFLICT (service_id) DO NOTHING
            """), {
                "service_id": service_id,
                "service_name": service_name,
                "port": port,
            })


from user_service.models import User  # noqa: E402, F401
from donation_service.models import Donation  # noqa: E402, F401
from delivery_service.models import Delivery  # noqa: E402, F401
