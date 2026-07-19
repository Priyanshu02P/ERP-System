import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.connection import get_db
from app.db.models.product import Product
from app.db.models.inventory import Inventory

@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_seed_synthetic_data(db_session, client):
    # Verify DB is initially empty
    assert db_session.query(Product).count() == 0
    
    # Run seed
    response = client.post("/api/v1/search/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Verify counts in DB
    assert db_session.query(Product).count() == 7
    assert db_session.query(Inventory).count() == 8
    
    # Re-running seed without clean should skip
    response = client.post("/api/v1/search/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    
    # Re-running with clean should succeed
    response = client.post("/api/v1/search/seed?clean=true")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

def test_check_availability(db_session, client):
    # Seed data first
    client.post("/api/v1/search/seed?clean=true")
    
    # Find some product IDs
    steel_rod = db_session.query(Product).filter(Product.code == "PROD-001").first()
    copper_wire = db_session.query(Product).filter(Product.code == "PROD-002").first()
    
    assert steel_rod is not None
    assert copper_wire is not None
    
    # Test checking availability
    # PROD-001 (Steel Rod) has quantity=120, reserved=15 -> available = 105
    # PROD-002 (Copper Wire) has quantity=50, reserved=0 -> available = 50
    
    payload = {
        "items": [
            {"product_id": steel_rod.id, "quantity": 10},      # available (10 <= 105)
            {"product_id": copper_wire.id, "quantity": 60},    # unavailable (60 > 50)
            {"product_id": 99999, "quantity": 5}               # does not exist
        ]
    }
    
    response = client.post("/api/v1/search/check-availability", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["all_available"] is False
    results = data["results"]
    assert len(results) == 3
    
    # Steel Rod result
    res_rod = next(r for r in results if r["product_id"] == steel_rod.id)
    assert res_rod["product_code"] == "PROD-001"
    assert res_rod["is_available"] is True
    assert res_rod["available_quantity"] == 105.0
    
    # Copper Wire result
    res_wire = next(r for r in results if r["product_id"] == copper_wire.id)
    assert res_wire["product_code"] == "PROD-002"
    assert res_wire["is_available"] is False
    assert res_wire["available_quantity"] == 50.0
    assert "Insufficient stock" in res_wire["remarks"]
    
    # Non-existent result
    res_none = next(r for r in results if r["product_id"] == 99999)
    assert res_none["product_code"] == "N/A"
    assert res_none["is_available"] is False
    assert res_none["remarks"] == "Product does not exist"
