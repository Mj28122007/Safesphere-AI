from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class AnalyzeRequest(BaseModel):
    latitude: float
    longitude: float
    location_name: str = ""
    demo_mode: bool = True
    scenario: str = "normal"

class FinancialPoint(BaseModel):
    label: str
    value: float

class FinancialResponse(BaseModel):
    index: float
    trend: str
    series: List[FinancialPoint]
    alerts: List[dict]
    entities: List[dict]

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "SafeSphere API online", "service": "risk-intelligence"}

def _get_json(url: str, params: dict):
    try:
        request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "SafeSphere/1.0"})
        with urllib.request.urlopen(request, timeout=6) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

def _demo_result(req: AnalyzeRequest):
    scenarios = {
        "normal": {"temperature_c": 24.0, "wind_speed_kmh": 14.0, "precipitation_probability": 12, "aqi": 42, "alerts": []},
        "flood": {"temperature_c": 27.5, "wind_speed_kmh": 34.0, "precipitation_probability": 92, "aqi": 58, "alerts": [{"title": "Flash Flood Warning — Coastal Zone", "severity": "CRITICAL", "priority_score": 92, "hazard_type": "Flood", "source": "SafeSphere simulation", "confidence": 0.91, "summary": "Heavy rainfall is expected to cause flash flooding in low-lying areas within 6 hours.", "why": "Rainfall intensity and proximity to a flood-prone area raise risk sharply.", "actions": ["Move to higher ground immediately", "Avoid underpasses and low-lying roads"], "avoid": ["Do not walk or drive through flood water"]}]},
        "earthquake": {"temperature_c": 25.0, "wind_speed_kmh": 12.0, "precipitation_probability": 18, "aqi": 48, "alerts": [{"title": "Moderate Earthquake Detected Nearby", "severity": "HIGH", "priority_score": 76, "hazard_type": "Earthquake", "source": "SafeSphere simulation", "confidence": 0.85, "summary": "A magnitude 5.4 earthquake was detected 42 km from this location.", "why": "Recent seismic activity above magnitude 5.0 within 50 km triggers a high-priority alert.", "actions": ["Check for structural damage", "Be prepared for aftershocks"], "avoid": ["Do not use elevators"]}]},
        "cyclone": {"temperature_c": 29.5, "wind_speed_kmh": 118.5, "precipitation_probability": 88, "aqi": 64, "alerts": [{"title": "Cyclone Warning — Category 2", "severity": "CRITICAL", "priority_score": 95, "hazard_type": "Cyclone", "source": "SafeSphere simulation", "confidence": 0.93, "summary": "Strong winds and heavy precipitation indicate a severe weather risk.", "why": "Wind speed and precipitation crossed the cyclone risk thresholds.", "actions": ["Secure loose outdoor objects", "Stock food, water, and medical supplies"], "avoid": ["Avoid coastal and low-lying areas"]}]},
    }
    item = scenarios.get(req.scenario, scenarios["normal"])
    return {"location": {"name": req.location_name or f"{req.latitude}, {req.longitude}", "latitude": req.latitude, "longitude": req.longitude}, "environment": {k: v for k, v in item.items() if k != "alerts"} | {"precipitation_mm": 0.5, "pm2_5": 12.4, "pm10": 22.0, "updated_at": datetime.now(timezone.utc).isoformat()}, "alerts": item["alerts"], "status": "success", "error_message": None, "is_demo_mode": True}

def _live_result(req: AnalyzeRequest):
    weather = _get_json("https://api.open-meteo.com/v1/forecast", {"latitude": req.latitude, "longitude": req.longitude, "current": "temperature_2m,precipitation,wind_speed_10m", "hourly": "precipitation_probability", "forecast_days": 1, "timezone": "auto"})
    air = _get_json("https://air-quality-api.open-meteo.com/v1/air-quality", {"latitude": req.latitude, "longitude": req.longitude, "current": "us_aqi,pm2_5,pm10", "timezone": "auto"})
    if not weather and not air:
        return _demo_result(req) | {"is_demo_mode": True, "error_message": "Live sources unavailable; showing demo data."}
    current = (weather or {}).get("current", {})
    air_current = (air or {}).get("current", {})
    env = {"temperature_c": current.get("temperature_2m"), "wind_speed_kmh": current.get("wind_speed_10m"), "precipitation_mm": current.get("precipitation"), "precipitation_probability": ((weather or {}).get("hourly", {}).get("precipitation_probability") or [None])[0], "aqi": air_current.get("us_aqi"), "pm2_5": air_current.get("pm2_5"), "pm10": air_current.get("pm10"), "updated_at": datetime.now(timezone.utc).isoformat()}
    alerts = []
    if (env["aqi"] or 0) >= 150: alerts.append({"title": "Elevated Air Quality Index", "severity": "HIGH", "priority_score": 75, "hazard_type": "Air Quality", "source": "Open-Meteo Air Quality API", "confidence": 0.75, "summary": f"Air Quality Index is currently {env['aqi']}, above the healthy range.", "why": "AQI crossed the configured alert threshold.", "actions": ["Limit prolonged outdoor activity"], "avoid": ["Avoid strenuous outdoor exercise"]})
    return {"location": {"name": req.location_name or f"{req.latitude}, {req.longitude}", "latitude": req.latitude, "longitude": req.longitude}, "environment": env, "alerts": alerts, "status": "success", "error_message": None, "is_demo_mode": False}

@api_router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    if not (-90 <= req.latitude <= 90 and -180 <= req.longitude <= 180):
        raise HTTPException(status_code=422, detail="Coordinates are outside valid ranges")
    return _demo_result(req) if req.demo_mode else _live_result(req)

@api_router.get("/financial", response_model=FinancialResponse)
async def financial():
    return FinancialResponse(index=72.4, trend="elevated", series=[], alerts=[{"title": "Supply Chain Volatility", "detail": "Rainfall and flooding may disrupt regional transport hubs in coastal corridors.", "region": "South India · East Coast", "severity": "HIGH"}, {"title": "Heat Wave Pressure", "detail": "Extreme heat may increase energy demand and impact industrial output.", "region": "North India · Inland hubs", "severity": "MODERATE"}], entities=[{"name": "Global Logix Corp", "region": "Chennai / Port routes", "level": "HIGH"}, {"name": "Aether Energy", "region": "Hyderabad / Grid belt", "level": "MED"}, {"name": "Titan Fab", "region": "Bengaluru / Industrial", "level": "LOW"}])

@api_router.get("/weather")
async def weather(lat: float, lon: float):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise HTTPException(status_code=422, detail="Invalid coordinates")
    data = _get_json("https://api.open-meteo.com/v1/forecast", {"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m", "timezone": "auto"})
    if not data: return {"status": "fallback", "current": {"temperature_2m": 24, "relative_humidity_2m": 62, "precipitation": 0.5, "weather_code": 1, "wind_speed_10m": 14}, "source": "DEMO FALLBACK"}
    return {"status": "live", "current": data.get("current", {}), "source": "Open-Meteo"}

@api_router.get("/map/heatmap/{layer}")
async def heatmap(layer: str, lat: float = 13.0827, lon: float = 80.2707):
    if layer not in {"flood", "heat", "storm", "air", "earthquake"}: raise HTTPException(status_code=422, detail="Unknown risk layer")
    seed = {"flood": .8, "heat": .65, "storm": .58, "air": .48, "earthquake": .34}[layer]
    points = [{"lat": lat + math.sin(i * 1.7) * .12, "lng": lon + math.cos(i * 1.3) * .12, "intensity": max(.1, min(1, seed + math.sin(i) * .18))} for i in range(28)]
    return {"layer": layer, "points": points, "source": "SafeSphere risk grid"}

@api_router.post("/map/route")
async def map_route(request: RouteRequest):
    coords = f"{request.start_lon},{request.start_lat};{request.end_lon},{request.end_lat}"
    data = _get_json("https://router.project-osrm.org/route/v1/driving/" + coords, {"overview": "full", "geometries": "geojson"})
    if data and data.get("routes"):
        route = data["routes"][0]
        return {"geometry": route["geometry"], "distance_m": route["distance"], "duration_s": route["duration"], "source": "OSRM"}
    return {"geometry": {"type": "LineString", "coordinates": [[request.start_lon, request.start_lat], [request.end_lon, request.end_lat]]}, "distance_m": 4200, "duration_s": 720, "source": "DEMO ROUTE"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()