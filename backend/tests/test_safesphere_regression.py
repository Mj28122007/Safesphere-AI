import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pilot-interface-v1.preview.emergentagent.com").rstrip("/")


def test_api_root_and_financial():
    root = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert root.status_code == 200
    assert root.json()["service"] == "risk-intelligence"
    financial = requests.get(f"{BASE_URL}/api/financial", timeout=15)
    assert financial.status_code == 200
    data = financial.json()
    assert data["index"] == 72.4 and data["series"] == []


def test_demo_analysis_and_invalid_coordinates():
    response = requests.post(f"{BASE_URL}/api/analyze", json={"latitude": 13.08, "longitude": 80.27, "location_name": "Chennai", "demo_mode": True, "scenario": "flood"}, timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert data["is_demo_mode"] is True and data["alerts"][0]["severity"] == "CRITICAL"
    invalid = requests.post(f"{BASE_URL}/api/analyze", json={"latitude": 100, "longitude": 0}, timeout=15)
    assert invalid.status_code == 422