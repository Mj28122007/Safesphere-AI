#!/usr/bin/env python3
"""
SafeSphere — Smart Alerts, single-file runnable demo
======================================================
Zero third-party dependencies: uses only the Python standard library
(including urllib for live API calls, no `requests`/`pydantic` needed).

RUN:
    python3 safesphere_demo.py

Then open:
    http://localhost:8000

This serves the restyled frontend (HTML/CSS/JS all inlined below) plus a
REAL, live hazard-analysis backend:
  - Open-Meteo Weather API      (temperature, wind, precipitation)
  - Open-Meteo Air Quality API  (AQI, PM2.5, PM10)
  - USGS Earthquake API         (nearby recent earthquakes)
No API keys are required for any of these.

As soon as you load the page or search/select a location, it fetches
current live conditions and runs the same deterministic hazard-detection
-> filtering -> priority-scoring pipeline described in the SafeSphere
design doc, condensed into this one file.

A "Demo mode" toggle in Settings is still available (off by default) for
presenting canned flood/earthquake/cyclone/multi-hazard scenarios without
depending on live conditions or network access.
"""
import json
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000

# ----------------------------------------------------------------------
# Mock hazard data — mirrors the shape of your real analyze_location_demo()
# ----------------------------------------------------------------------

def mock_environment(scenario):
    base = {
        "temperature_c": 29.5, "precipitation_mm": 0.5, "precipitation_probability": 10,
        "wind_speed_kmh": 12.0, "aqi": 58, "pm2_5": 18.4, "pm10": 30.1,
    }
    overrides = {
        "flood": {"precipitation_mm": 68.4, "precipitation_probability": 92, "wind_speed_kmh": 34.0},
        "cyclone": {"wind_speed_kmh": 118.5, "precipitation_mm": 45.2, "precipitation_probability": 88},
        "earthquake": {},
        "multi": {"precipitation_mm": 55.0, "precipitation_probability": 85, "wind_speed_kmh": 95.0, "aqi": 152},
    }
    env = {**base, **overrides.get(scenario, {})}
    env["updated_at"] = datetime.now(timezone.utc).isoformat()
    return env


def mock_alerts(scenario):
    now = datetime.now(timezone.utc).isoformat()
    catalog = {
        "flood": [{
            "title": "Flash Flood Warning \u2014 Coastal Zone", "severity": "CRITICAL", "priority_score": 92,
            "hazard_type": "Flood", "source": "IMD", "confidence": 0.91, "timestamp": now,
            "distance_km": 3.2, "location": "Marina Beach sector",
            "summary": "Heavy rainfall is expected to cause flash flooding in low-lying coastal areas within 6 hours.",
            "why": "Sustained rainfall above 40mm/hr combined with high tide conditions raises flood risk sharply.",
            "priority_breakdown": {"factors": ["Rainfall intensity: 30 pts", "Proximity to coast: 25 pts", "Tide timing: 20 pts", "Historical flood zone: 17 pts"], "score": 92, "level": "CRITICAL"},
            "actions": ["Move to higher ground immediately", "Avoid underpasses and low-lying roads", "Keep an emergency kit ready"],
            "avoid": ["Do not walk or drive through flood water", "Avoid coastal roads"],
        }],
        "earthquake": [{
            "title": "Moderate Earthquake Detected Nearby", "severity": "HIGH", "priority_score": 76,
            "hazard_type": "Earthquake", "source": "USGS", "confidence": 0.85, "timestamp": now,
            "distance_km": 42.0, "location": "18km NE of epicenter",
            "summary": "A magnitude 5.4 earthquake was detected 42km from this location. Aftershocks are possible.",
            "why": "Recent seismic activity above magnitude 5.0 within 50km triggers a high-priority alert.",
            "priority_breakdown": {"factors": ["Magnitude: 35 pts", "Distance: 24 pts", "Aftershock likelihood: 17 pts"], "score": 76, "level": "HIGH"},
            "actions": ["Check for structural damage before re-entering buildings", "Be prepared for aftershocks", "Keep emergency contacts handy"],
            "avoid": ["Do not use elevators", "Avoid damaged structures"],
        }],
        "cyclone": [{
            "title": "Cyclone Warning \u2014 Category 2", "severity": "CRITICAL", "priority_score": 95,
            "hazard_type": "Cyclone", "source": "IMD", "confidence": 0.93, "timestamp": now,
            "distance_km": 85.0, "location": "Bay of Bengal, approaching coast",
            "summary": "A category 2 cyclone is approaching with sustained winds over 110 km/h. Landfall expected within 18 hours.",
            "why": "Wind speeds and pressure drop match category 2 cyclone thresholds with a confirmed landfall track.",
            "priority_breakdown": {"factors": ["Wind speed: 32 pts", "Landfall proximity: 28 pts", "Population density: 20 pts", "Track confidence: 15 pts"], "score": 95, "level": "CRITICAL"},
            "actions": ["Secure loose outdoor objects", "Stock food, water, and medical supplies", "Follow evacuation orders if issued"],
            "avoid": ["Do not travel unless evacuating", "Avoid coastal and low-lying areas"],
        }],
        "multi": [],
        "normal": [],
    }
    if scenario == "multi":
        return catalog["flood"] + [{**catalog["earthquake"][0], "priority_score": 64, "severity": "MODERATE"}]
    return catalog.get(scenario, [])


def analyze_demo(latitude, longitude, location_name, scenario):
    return {
        "location": {"name": location_name, "latitude": latitude, "longitude": longitude},
        "environment": mock_environment(scenario),
        "alerts": mock_alerts(scenario),
        "status": "success",
        "error_message": None,
        "is_demo_mode": True,
    }


# ----------------------------------------------------------------------
# LIVE data — real weather / air-quality / earthquake APIs
# Still zero third-party dependencies: uses urllib from the standard
# library instead of `requests`, so this file stays a single-file,
# pip-install-free demo you can drop straight into a repo.
#
# No API keys needed — Open-Meteo and USGS are both free, keyless APIs.
# ----------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS = 8

# Same prototype thresholds/weights described in the SafeSphere design doc.
# Kept here (rather than a separate config.py) so this stays single-file.
EARTHQUAKE_RULES = [  # (min_magnitude, max_distance_km, severity)
    (6.0, 500, "CRITICAL"),
    (5.0, 300, "HIGH"),
    (4.0, 150, "MODERATE"),
    (3.5, 50, "LOW"),
]
FLOOD_RULES = [  # (min_probability_pct, min_precip_mm, severity)
    (85, 20, "CRITICAL"),
    (70, 10, "HIGH"),
    (50, 5, "MODERATE"),
    (30, 2, "LOW"),
]
CYCLONE_RULES = [  # (min_wind_kmh, min_precip_mm, severity)
    (100, 15, "CRITICAL"),
    (70, 8, "HIGH"),
    (50, 3, "MODERATE"),
    (35, 0, "LOW"),
]
AQI_ALERT_THRESHOLD = 150
SEVERITY_SCORE_MAP = {"LOW": 25, "MODERATE": 50, "HIGH": 75, "CRITICAL": 100}
CONFIDENCE_SCORE_MAP = {"LOW": 40, "MEDIUM": 70, "HIGH": 95}
CONFIDENCE_FRACTION_MAP = {"LOW": 0.55, "MEDIUM": 0.75, "HIGH": 0.93}
PRIORITY_TIERS = [  # (min_score, max_score, tier)
    (76, 100, "CRITICAL"),
    (51, 75, "HIGH"),
    (26, 50, "MODERATE"),
    (0, 25, "LOW"),
]
PROXIMITY_MAX_RELEVANT_KM = 500
SEVERITY_WEIGHT, PROXIMITY_WEIGHT, IMMEDIACY_WEIGHT, CONFIDENCE_WEIGHT = 0.40, 0.30, 0.20, 0.10


def _http_get_json(url, params):
    """GET a URL with query params and parse the JSON response. Never
    raises — returns None on any failure so one bad API never crashes the
    whole analysis."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        request = urllib.request.Request(
            full_url, headers={"User-Agent": "SafeSphere-Demo/1.0"}
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001 - deliberately broad, we log and continue
        print(f"[SafeSphere] API request failed ({url}): {error}")
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometers."""
    R = 6371.0
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
    d_lat = lat2_r - lat1_r
    d_lon = lon2_r - lon1_r
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(d_lon / 2) ** 2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


def fetch_live_weather(lat, lon):
    """Open-Meteo Weather API -> clean dict, or None on failure."""
    data = _http_get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "hourly": "precipitation,precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    if not data:
        return None

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    hourly_prob = hourly.get("precipitation_probability", [])

    return {
        "temperature_c": current.get("temperature_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "precipitation_mm": current.get("precipitation"),
        "precipitation_probability": hourly_prob[0] if hourly_prob else None,
        "forecast_precipitation": hourly.get("precipitation", []),
        "forecast_precipitation_probability": hourly_prob,
    }


def fetch_live_air_quality(lat, lon):
    """Open-Meteo Air Quality API -> clean dict, or None on failure."""
    data = _http_get_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        {"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5,pm10", "timezone": "auto"},
    )
    if not data:
        return None

    current = data.get("current", {})
    aqi, pm2_5, pm10 = current.get("us_aqi"), current.get("pm2_5"), current.get("pm10")
    if aqi is None and pm2_5 is None and pm10 is None:
        return None
    return {"aqi": aqi, "pm2_5": pm2_5, "pm10": pm10}


def fetch_live_earthquakes(lat, lon, radius_km=500, days=3, min_magnitude=3.5):
    """USGS Earthquake API -> list of nearby events (possibly empty), never None."""
    start_time = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    data = _http_get_json(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        {
            "format": "geojson",
            "latitude": lat,
            "longitude": lon,
            "maxradiuskm": radius_km,
            "starttime": start_time,
            "minmagnitude": min_magnitude,
            "orderby": "time",
        },
    )
    if not data:
        return []

    events = []
    for feature in data.get("features", []):
        try:
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) < 3 or props.get("mag") is None:
                continue
            quake_lon, quake_lat, depth_km = coords[0], coords[1], coords[2]
            distance_km = haversine_km(lat, lon, quake_lat, quake_lon)
            if distance_km > radius_km:
                continue
            time_millis = props.get("time")
            event_time = (
                datetime.fromtimestamp(time_millis / 1000, tz=timezone.utc).isoformat()
                if time_millis else None
            )
            events.append({
                "magnitude": props.get("mag"),
                "place": props.get("place"),
                "distance_km": distance_km,
                "depth_km": depth_km,
                "time": event_time,
            })
        except (KeyError, TypeError, IndexError):
            continue

    events.sort(key=lambda e: (-e["magnitude"], e["distance_km"]))
    return events


def _classify(rules, value_a, value_b):
    """Shared helper: walk a rules list of (threshold_a, threshold_b, label)
    from strongest to weakest and return the first label both values
    qualify for, or None."""
    for threshold_a, threshold_b, label in rules:
        if value_a >= threshold_a and value_b >= threshold_b:
            return label
    return None


def _priority_score(severity, distance_km, is_recent, confidence_label):
    """Explainable 0-100 priority score. Returns (score, tier, factor_lines)."""
    severity_score = SEVERITY_SCORE_MAP.get(severity, 0)
    if distance_km is None:
        proximity_score = 50
    elif distance_km >= PROXIMITY_MAX_RELEVANT_KM:
        proximity_score = 0
    else:
        proximity_score = round(100 * (1 - distance_km / PROXIMITY_MAX_RELEVANT_KM))
    immediacy_score = 90 if is_recent else 55
    confidence_score = CONFIDENCE_SCORE_MAP.get(confidence_label, 50)

    raw = (
        SEVERITY_WEIGHT * severity_score
        + PROXIMITY_WEIGHT * proximity_score
        + IMMEDIACY_WEIGHT * immediacy_score
        + CONFIDENCE_WEIGHT * confidence_score
    )
    score = round(max(0, min(100, raw)))
    tier = next((t for lo, hi, t in PRIORITY_TIERS if lo <= score <= hi), "LOW")

    factors = [
        f"Severity ({severity.title()}): {round(SEVERITY_WEIGHT * severity_score)} pts",
        f"Proximity: {round(PROXIMITY_WEIGHT * proximity_score)} pts",
        f"Immediacy: {round(IMMEDIACY_WEIGHT * immediacy_score)} pts",
        f"Data confidence: {round(CONFIDENCE_WEIGHT * confidence_score)} pts",
    ]
    return score, tier, factors


def _build_earthquake_alert(event, location_name, now_iso):
    # Earthquake rules need "distance <= max" rather than ">=", so we don't
    # use the shared _classify() helper here — a small explicit loop instead.
    severity = None
    for min_mag, max_dist, label in EARTHQUAKE_RULES:
        if event["magnitude"] >= min_mag and event["distance_km"] <= max_dist:
            severity = label
            break
    if severity is None:
        return None

    score, tier, factors = _priority_score(severity, event["distance_km"], True, "HIGH")
    magnitude, distance = event["magnitude"], event["distance_km"]

    return {
        "title": "Nearby Earthquake Detected",
        "severity": severity,
        "priority_score": score,
        "hazard_type": "Earthquake",
        "source": "USGS Earthquake API",
        "confidence": CONFIDENCE_FRACTION_MAP["HIGH"],
        "timestamp": now_iso,
        "distance_km": distance,
        "location": event.get("place") or location_name,
        "summary": (
            f"A magnitude {magnitude} earthquake was recorded approximately "
            f"{distance} km from your current location."
        ),
        "why": (
            f"This event met our magnitude/distance rule for {severity.title()} "
            f"severity based on live USGS data."
        ),
        "priority_breakdown": {"factors": factors, "score": score, "level": tier},
        "actions": [
            "Stay alert for possible aftershocks",
            "Check for structural damage before re-entering buildings",
            "Keep emergency contacts and a charged phone handy",
        ],
        "avoid": ["Do not use elevators until it's confirmed safe", "Avoid visibly damaged structures"],
    }


def _build_flood_alert(weather, location_name, now_iso):
    precip = weather.get("precipitation_mm") or 0
    prob = weather.get("precipitation_probability") or 0
    severity = _classify(FLOOD_RULES, prob, precip)
    if severity is None:
        return None

    score, tier, factors = _priority_score(severity, None, True, "MEDIUM")
    return {
        "title": "Flood-Risk Indicator",
        "severity": severity,
        "priority_score": score,
        "hazard_type": "Flood",
        "source": "Open-Meteo Weather API",
        "confidence": CONFIDENCE_FRACTION_MAP["MEDIUM"],
        "timestamp": now_iso,
        "distance_km": None,
        "location": location_name,
        "summary": (
            f"Rain is expected around your location with a {prob}% precipitation "
            f"probability and roughly {precip} mm of rainfall, raising flood risk."
        ),
        "why": (
            "This is a heuristic risk indicator based on live precipitation "
            "probability and intensity — it is NOT an official flood warning."
        ),
        "priority_breakdown": {"factors": factors, "score": score, "level": tier},
        "actions": [
            "Avoid low-lying and flood-prone routes if traveling",
            "Keep an eye on official local alerts",
            "Have an emergency kit ready in case conditions worsen",
        ],
        "avoid": ["Do not walk or drive through flooded roads", "Avoid underpasses during heavy rain"],
    }


def _build_cyclone_alert(weather, location_name, now_iso):
    wind = weather.get("wind_speed_kmh") or 0
    precip = weather.get("precipitation_mm") or 0
    severity = _classify(CYCLONE_RULES, wind, precip)
    if severity is None:
        return None

    score, tier, factors = _priority_score(severity, None, True, "MEDIUM")
    return {
        "title": "Cyclone-Related Weather Risk",
        "severity": severity,
        "priority_score": score,
        "hazard_type": "Cyclone",
        "source": "Open-Meteo Weather API",
        "confidence": CONFIDENCE_FRACTION_MAP["MEDIUM"],
        "timestamp": now_iso,
        "distance_km": None,
        "location": location_name,
        "summary": (
            f"Strong winds of about {wind} km/h combined with {precip} mm of "
            f"precipitation indicate elevated cyclone-related weather risk."
        ),
        "why": (
            "This is a heuristic wind/precipitation risk indicator based on "
            "live forecast data — it is NOT an official cyclone warning."
        ),
        "priority_breakdown": {"factors": factors, "score": score, "level": tier},
        "actions": [
            "Secure loose outdoor objects",
            "Stock food, water, and basic medical supplies",
            "Follow official evacuation guidance if it is issued",
        ],
        "avoid": ["Avoid unnecessary travel", "Avoid coastal and low-lying areas"],
    }


def _build_air_quality_alert(air_quality, location_name, now_iso):
    aqi = air_quality.get("aqi")
    if aqi is None or aqi < AQI_ALERT_THRESHOLD:
        return None

    severity = "MODERATE" if aqi < 200 else "HIGH"
    score, tier, factors = _priority_score(severity, None, True, "MEDIUM")
    return {
        "title": "Elevated Air Quality Index",
        "severity": severity,
        "priority_score": score,
        "hazard_type": "Air Quality",
        "source": "Open-Meteo Air Quality API",
        "confidence": CONFIDENCE_FRACTION_MAP["MEDIUM"],
        "timestamp": now_iso,
        "distance_km": None,
        "location": location_name,
        "summary": f"Air Quality Index is currently {aqi}, above the healthy range.",
        "why": "AQI crossed the configured alert threshold based on live sensor data.",
        "priority_breakdown": {"factors": factors, "score": score, "level": tier},
        "actions": ["Limit prolonged outdoor activity", "Consider a mask if sensitive to air quality"],
        "avoid": ["Avoid strenuous outdoor exercise"],
    }


def analyze_live(latitude, longitude, location_name):
    """
    Fetch REAL weather, air-quality, and earthquake data for a location and
    turn it into the same alert shape the frontend already renders.

    This mirrors the deterministic hazard-detection -> filtering ->
    priority-scoring pipeline from the full SafeSphere module, condensed
    into one file. Any single API failing does not stop the others.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    location_name = location_name or f"{latitude}, {longitude}"

    weather = fetch_live_weather(latitude, longitude)
    air_quality = fetch_live_air_quality(latitude, longitude)
    earthquakes = fetch_live_earthquakes(latitude, longitude)

    environment = {
        "temperature_c": weather.get("temperature_c") if weather else None,
        "precipitation_mm": weather.get("precipitation_mm") if weather else None,
        "precipitation_probability": weather.get("precipitation_probability") if weather else None,
        "wind_speed_kmh": weather.get("wind_speed_kmh") if weather else None,
        "aqi": air_quality.get("aqi") if air_quality else None,
        "pm2_5": air_quality.get("pm2_5") if air_quality else None,
        "pm10": air_quality.get("pm10") if air_quality else None,
        "updated_at": now_iso,
    }

    alerts = []
    if earthquakes:
        # Only ever surface the single most relevant (closest+strongest)
        # earthquake, to avoid alert overload.
        alert = _build_earthquake_alert(earthquakes[0], location_name, now_iso)
        if alert:
            alerts.append(alert)
    if weather:
        flood_alert = _build_flood_alert(weather, location_name, now_iso)
        if flood_alert:
            alerts.append(flood_alert)
        cyclone_alert = _build_cyclone_alert(weather, location_name, now_iso)
        if cyclone_alert:
            alerts.append(cyclone_alert)
    if air_quality:
        aqi_alert = _build_air_quality_alert(air_quality, location_name, now_iso)
        if aqi_alert:
            alerts.append(aqi_alert)

    alerts.sort(key=lambda a: a["priority_score"], reverse=True)

    if weather is None and air_quality is None and not earthquakes:
        return {
            "location": {"name": location_name, "latitude": latitude, "longitude": longitude},
            "environment": environment,
            "alerts": [],
            "status": "error",
            "error_message": "Could not reach any live data source. Check your network connection or try demo mode.",
            "is_demo_mode": False,
        }

    return {
        "location": {"name": location_name, "latitude": latitude, "longitude": longitude},
        "environment": environment,
        "alerts": alerts,
        "status": "success",
        "error_message": None,
        "is_demo_mode": False,
    }


# ----------------------------------------------------------------------
# Frontend (HTML + inlined CSS/JS)
# ----------------------------------------------------------------------

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>SafeSphere — Smart Alerts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;0,900;1,500&display=swap" rel="stylesheet">
<style>
/* ============================================================
   SafeSphere — design tokens
   Matches the team dashboard: deep-space background, Playfair
   Display throughout, glassy dark cards, cyan/gold/red accents.
   ============================================================ */
:root {
  --bg: #05060a;
  --bg-deep: #0a0d16;

  --surface: rgba(18, 20, 29, 0.62);
  --surface-strong: rgba(22, 25, 35, 0.8);
  --surface-border: rgba(255, 255, 255, 0.09);
  --surface-border-hover: rgba(255, 255, 255, 0.18);

  --text-primary: #f4f1e8;
  --text-secondary: #9aa3b5;
  --text-tertiary: #6b7280;

  --accent-cyan: #5fd3e8;
  --accent-gold: #f0b94d;

  --sev-critical: #ff5c5c;
  --sev-high: #ff9d4d;
  --sev-moderate: #f2ce5a;
  --sev-low: #4fd88b;

  --radius-lg: 20px;
  --radius-md: 14px;
  --radius-sm: 9px;

  --font-display: "Playfair Display", "Iowan Old Style", serif;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text-primary);
  font-family: var(--font-display);
  -webkit-font-smoothing: antialiased;
}

body {
  min-height: 100vh;
  position: relative;
  overflow-x: hidden;
}

a { color: var(--accent-cyan); }

:focus-visible {
  outline: 2px solid var(--accent-cyan);
  outline-offset: 3px;
}

#starfield {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}

/* ============================================================
   Hero
   ============================================================ */
.hero {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  padding: 84px 6vw 96px;
  background:
    radial-gradient(60% 55% at 78% 30%, rgba(95, 211, 232, 0.14), transparent 70%),
    radial-gradient(45% 40% at 15% 80%, rgba(240, 185, 77, 0.06), transparent 70%),
    linear-gradient(180deg, #070a12 0%, #05060a 65%, #05060a 100%);
  border-bottom: 1px solid var(--surface-border);
  overflow: hidden;
}

.hero__glow {
  position: absolute;
  right: -10%;
  top: 50%;
  transform: translateY(-50%);
  width: 480px;
  height: 480px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #1c3a52 0%, #0d1a2b 45%, transparent 72%);
  box-shadow: 0 0 140px 40px rgba(95, 211, 232, 0.06);
  z-index: -1;
}

.hero__menu {
  position: absolute;
  top: 24px;
  left: 6vw;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: 1px solid var(--surface-border);
  background: var(--surface);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.hero__menu:hover { border-color: var(--surface-border-hover); background: var(--surface-strong); }

.hero__inner {
  width: 100%;
  max-width: 620px;
}

.hero__eyebrow {
  margin: 0 0 6px;
  color: var(--accent-cyan);
  font-size: 0.95rem;
  letter-spacing: 0.02em;
  font-style: italic;
}

.hero__brand {
  margin: 0 0 40px;
  font-weight: 700;
  font-size: clamp(2.6rem, 6vw, 4.2rem);
  line-height: 1;
  letter-spacing: -0.01em;
}

.hero__search label {
  display: block;
  font-size: 1.15rem;
  font-weight: 600;
  margin-bottom: 10px;
}

.search-row {
  display: flex;
  gap: 10px;
}

#locationInput {
  flex: 1;
  min-width: 0;
  background: rgba(8, 9, 14, 0.7);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 1.02rem;
  padding: 14px 18px;
  transition: border-color 0.15s ease;
}
#locationInput::placeholder { color: var(--text-tertiary); font-style: italic; }
#locationInput:focus { border-color: var(--accent-cyan); }

.btn-analyze {
  border: none;
  border-radius: var(--radius-md);
  padding: 0 26px;
  background: linear-gradient(135deg, var(--accent-cyan), #3fa8c2);
  color: #071019;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.02rem;
  cursor: pointer;
  transition: transform 0.12s ease, filter 0.12s ease;
  white-space: nowrap;
}
.btn-analyze:hover { filter: brightness(1.08); }
.btn-analyze:active { transform: scale(0.98); }
.btn-analyze:disabled { opacity: 0.6; cursor: progress; }

.search-error {
  color: var(--sev-critical);
  font-size: 0.92rem;
  margin: 10px 2px 0;
}

.presets {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.preset-chip {
  border: 1px solid var(--surface-border);
  background: var(--surface);
  color: var(--text-secondary);
  font-family: var(--font-display);
  font-size: 0.95rem;
  padding: 8px 16px;
  border-radius: 999px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}
.preset-chip:hover {
  border-color: var(--surface-border-hover);
  color: var(--text-primary);
  background: var(--surface-strong);
}
.preset-chip[aria-pressed="true"] {
  border-color: var(--accent-cyan);
  color: var(--accent-cyan);
}

.hidden { display: none !important; }

/* ============================================================
   Settings drawer
   ============================================================ */
.drawer-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 20;
}

.drawer {
  position: fixed;
  top: 0;
  left: 0;
  height: 100%;
  width: min(340px, 88vw);
  z-index: 21;
  transform: translateX(0);
  transition: transform 0.22s ease;
}
.drawer.hidden { transform: translateX(-104%); }

.drawer__panel {
  height: 100%;
  background: var(--bg-deep);
  border-right: 1px solid var(--surface-border);
  padding: 26px 24px;
  overflow-y: auto;
}

.drawer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
}
.drawer__head h2 { margin: 0; font-size: 1.5rem; }

.drawer__close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
}
.drawer__close:hover { color: var(--text-primary); }

.drawer__row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 0;
  border-bottom: 1px solid var(--surface-border);
}
.drawer__row--stack { display: block; }

.drawer__label { margin: 0 0 4px; font-weight: 600; font-size: 1.02rem; }
.drawer__hint { margin: 0; font-size: 0.88rem; color: var(--text-secondary); font-style: italic; }
.drawer__footnote {
  margin-top: 24px;
  font-size: 0.85rem;
  color: var(--text-tertiary);
  font-style: italic;
  line-height: 1.5;
}

.switch { flex-shrink: 0; }
.switch input { position: absolute; opacity: 0; width: 0; height: 0; }
.switch__track {
  display: block;
  width: 44px;
  height: 24px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--surface-border);
  position: relative;
  cursor: pointer;
  transition: background 0.15s ease;
}
.switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--text-secondary);
  transition: transform 0.15s ease, background 0.15s ease;
}
.switch input:checked + .switch__track { background: rgba(95, 211, 232, 0.18); border-color: var(--accent-cyan); }
.switch input:checked + .switch__track .switch__thumb { transform: translateX(20px); background: var(--accent-cyan); }

#scenarioSelect, .drawer__coords input {
  width: 100%;
  background: rgba(8, 9, 14, 0.7);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 0.98rem;
  padding: 10px 12px;
  margin-top: 8px;
}
.drawer__coords { display: flex; gap: 10px; }
.drawer__coords input { margin-top: 0; }

/* ============================================================
   Stat cards
   ============================================================ */
.stats {
  position: relative;
  z-index: 1;
  max-width: 1180px;
  margin: -56px auto 0;
  padding: 0 6vw;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}

.stat-card {
  background: var(--surface);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  padding: 22px 18px;
  text-align: center;
}

.stat-card__icon { font-size: 1.5rem; margin-bottom: 8px; }
.stat-card__label {
  margin: 0 0 10px;
  font-size: 0.8rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-secondary);
  font-style: normal;
}
.stat-card__value { margin: 0; font-size: 2.1rem; font-weight: 700; }
.stat-card--temp .stat-card__value { color: var(--accent-gold); }
.stat-card--wind .stat-card__value,
.stat-card--precip .stat-card__value { color: var(--accent-cyan); }
.stat-card--aqi .stat-card__value { color: var(--text-primary); }

.stats__caption {
  max-width: 1180px;
  margin: 14px auto 0;
  padding: 0 6vw;
  color: var(--text-tertiary);
  font-size: 0.85rem;
  font-style: italic;
  min-height: 1.2em;
}

/* ============================================================
   Alerts
   ============================================================ */
.alerts-section {
  max-width: 1180px;
  margin: 56px auto 0;
  padding: 0 6vw 40px;
  position: relative;
  z-index: 1;
}

.alerts-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}
.alerts-section__head h2 { margin: 0; font-size: 1.9rem; }
.alerts-section__summary { margin: 0; color: var(--text-secondary); font-style: italic; }

.alerts-empty {
  color: var(--text-secondary);
  font-style: italic;
  padding: 30px 0;
}

.alerts-list { display: flex; flex-direction: column; gap: 16px; }

.alert-card {
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-left: 3px solid var(--sev-color, var(--accent-cyan));
  border-radius: var(--radius-md);
  padding: 22px 24px;
}

.alert-card--critical { --sev-color: var(--sev-critical); }
.alert-card--high { --sev-color: var(--sev-high); }
.alert-card--moderate { --sev-color: var(--sev-moderate); }
.alert-card--low { --sev-color: var(--sev-low); }

.alert-card__head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.alert-card__badge {
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--sev-color);
  border: 1px solid var(--sev-color);
  background: color-mix(in srgb, var(--sev-color) 12%, transparent);
}

.alert-card__title { margin: 0; font-size: 1.3rem; flex: 1; min-width: 200px; }
.alert-card__score { color: var(--text-secondary); font-size: 0.95rem; font-style: italic; }

.alert-card__tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.alert-card__tag {
  font-size: 0.82rem;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--surface-border);
  border-radius: 6px;
  padding: 3px 10px;
}

.alert-card__summary {
  margin: 0 0 16px;
  line-height: 1.65;
  color: var(--text-primary);
}

.alert-card details {
  border-top: 1px solid var(--surface-border);
  padding-top: 12px;
  margin-top: 12px;
}
.alert-card summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--accent-cyan);
  font-size: 0.98rem;
}
.alert-card details[open] summary { margin-bottom: 10px; }
.alert-card details p, .alert-card details li { color: var(--text-secondary); line-height: 1.6; }

.priority-breakdown { margin: 10px 0 0; padding-left: 20px; }
.priority-breakdown__total { color: var(--text-primary); font-weight: 600; margin-top: 8px; }

.action-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 16px;
}
.action-columns h4 {
  margin: 0 0 8px;
  font-size: 0.95rem;
  color: var(--text-primary);
}
.action-columns ul { margin: 0; padding-left: 20px; }
.action-columns li { color: var(--text-secondary); line-height: 1.6; margin-bottom: 4px; }
.action-columns--do h4 { color: var(--sev-low); }
.action-columns--avoid h4 { color: var(--sev-critical); }

.extra-details dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 14px;
  margin: 0;
}
.extra-details dt { color: var(--text-tertiary); }
.extra-details dd { margin: 0; color: var(--text-secondary); }

/* ============================================================
   Footer
   ============================================================ */
.site-footer {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 34px 6vw 50px;
  color: var(--text-tertiary);
  border-top: 1px solid var(--surface-border);
}
.site-footer p { margin: 0 0 6px; }
.site-footer__fine { font-size: 0.82rem; font-style: italic; }

/* ============================================================
   Responsive
   ============================================================ */
@media (max-width: 860px) {
  .stats { grid-template-columns: repeat(2, 1fr); margin-top: -40px; }
  .action-columns { grid-template-columns: 1fr; }
  .hero { min-height: auto; padding-top: 76px; padding-bottom: 56px; }
}

@media (max-width: 520px) {
  .search-row { flex-direction: column; }
  .btn-analyze { padding: 14px; }
  .stats { grid-template-columns: 1fr 1fr; gap: 12px; }
  .stat-card { padding: 16px 10px; }
  .stat-card__value { font-size: 1.6rem; }
}

</style>
</head>
<body>

<canvas id="starfield" aria-hidden="true"></canvas>

<header class="hero">
  <button id="menuBtn" class="hero__menu" aria-haspopup="true" aria-expanded="false" aria-controls="settingsDrawer" title="Settings">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>
  </button>

  <div class="hero__glow" aria-hidden="true"></div>

  <div class="hero__inner">
    <p class="hero__eyebrow">Smart Alerts</p>
    <h1 class="hero__brand">SafeSphere</h1>

    <div class="hero__search">
      <label for="locationInput">Enter Location</label>
      <div class="search-row">
        <input id="locationInput" type="text" placeholder="Search coordinates, sector, or city..." autocomplete="off" value="Chennai, India" />
        <button id="analyzeBtn" class="btn-analyze">Analyze</button>
      </div>
      <p id="searchError" class="search-error hidden"></p>

      <div class="presets" id="presets" role="group" aria-label="Quick locations"></div>
    </div>
  </div>
</header>

<aside id="settingsDrawer" class="drawer hidden" aria-hidden="true">
  <div class="drawer__panel">
    <div class="drawer__head">
      <h2>Settings</h2>
      <button id="closeDrawer" class="drawer__close" aria-label="Close settings">&times;</button>
    </div>

    <div class="drawer__row">
      <label class="switch">
        <input type="checkbox" id="demoToggle" />
        <span class="switch__track"><span class="switch__thumb"></span></span>
      </label>
      <div>
        <p class="drawer__label">Demo mode</p>
        <p class="drawer__hint" id="demoHint">Fetching live data from weather, air-quality, and earthquake APIs.</p>
      </div>
    </div>

    <div class="drawer__row drawer__row--stack" id="scenarioRow">
      <p class="drawer__label">Scenario</p>
      <select id="scenarioSelect">
        <option value="normal">Normal conditions</option>
        <option value="flood">Flood</option>
        <option value="earthquake">Earthquake</option>
        <option value="cyclone">Cyclone</option>
        <option value="multi">Multiple hazards</option>
      </select>
    </div>

    <div class="drawer__row drawer__row--stack">
      <p class="drawer__label">Coordinates</p>
      <div class="drawer__coords">
        <input id="latInput" type="number" step="0.0001" value="13.0827" aria-label="Latitude" />
        <input id="lonInput" type="number" step="0.0001" value="80.2707" aria-label="Longitude" />
      </div>
    </div>

    <p class="drawer__footnote">SafeSphere is a decision-support tool, not an official warning system.</p>
  </div>
</aside>
<div id="drawerScrim" class="drawer-scrim hidden"></div>

<main>
  <section class="stats" id="statsSection" aria-live="polite">
    <!-- populated by app.js -->
  </section>
  <p class="stats__caption" id="updatedAt"></p>

  <section class="alerts-section">
    <div class="alerts-section__head">
      <h2>Safety Alerts</h2>
      <p id="alertsSummary" class="alerts-section__summary"></p>
    </div>
    <div id="alertsList" class="alerts-list" aria-live="polite">
      <p class="alerts-empty">Enter a location and choose Analyze to check current hazards.</p>
    </div>
  </section>
</main>

<footer class="site-footer">
  <p><strong>SafeSphere</strong> — Personal risk intelligence for safer travel.</p>
  <p class="site-footer__fine">This is a decision-support tool, not an official disaster warning system. Always follow guidance from local authorities and official sources.</p>
</footer>

<script>
// ============================================================
// SafeSphere — frontend logic
// Talks to the FastAPI backend at /api/analyze (same origin).
// ============================================================

const API_BASE = ""; // same-origin deployment; set e.g. "https://api.yourteam.com" if split

const PRESETS = [
  { name: "Chennai", lat: 13.0827, lon: 80.2707 },
  { name: "Delhi", lat: 28.7041, lon: 77.1025 },
  { name: "Mumbai", lat: 19.0760, lon: 72.8777 },
  { name: "Tokyo", lat: 35.6762, lon: 139.6503 },
  { name: "San Francisco", lat: 37.7749, lon: -122.4194 },
];

const state = {
  locationName: "Chennai, India",
  lat: 13.0827,
  lon: 80.2707,
  demoMode: false,
  scenario: "normal",
};

// ---------- Starfield background ----------
(function starfield() {
  const canvas = document.getElementById("starfield");
  const ctx = canvas.getContext("2d");
  let stars = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = document.body.scrollHeight;
    const count = Math.floor((canvas.width * canvas.height) / 9000);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.1 + 0.2,
      a: Math.random() * 0.6 + 0.15,
    }));
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of stars) {
      ctx.beginPath();
      ctx.fillStyle = `rgba(244, 241, 232, ${s.a})`;
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  window.addEventListener("resize", resize);
  new ResizeObserver(resize).observe(document.body);
  resize();
})();

// ---------- Presets ----------
const presetsEl = document.getElementById("presets");
PRESETS.forEach((p) => {
  const btn = document.createElement("button");
  btn.className = "preset-chip";
  btn.type = "button";
  btn.textContent = p.name;
  btn.setAttribute("aria-pressed", "false");
  btn.addEventListener("click", () => {
    document.getElementById("locationInput").value = p.name;
    document.getElementById("latInput").value = p.lat;
    document.getElementById("lonInput").value = p.lon;
    state.locationName = p.name;
    state.lat = p.lat;
    state.lon = p.lon;
    markActivePreset(p.name);
    runAnalysis();
  });
  presetsEl.appendChild(btn);
});

function markActivePreset(name) {
  const lower = (name || "").toLowerCase();
  [...presetsEl.children].forEach((c) => {
    c.setAttribute("aria-pressed", lower.includes(c.textContent.toLowerCase()) ? "true" : "false");
  });
}

// ---------- Location resolution from free text ----------
function resolveLocation(query) {
  const trimmed = query.trim();
  if (!trimmed) return null;

  const preset = PRESETS.find((p) => p.name.toLowerCase().includes(trimmed.toLowerCase()));
  if (preset) return { name: preset.name, lat: preset.lat, lon: preset.lon };

  const coordMatch = trimmed.match(/^(-?\\d+(?:\\.\\d+)?)\\s*,\\s*(-?\\d+(?:\\.\\d+)?)$/);
  if (coordMatch) {
    const lat = parseFloat(coordMatch[1]);
    const lon = parseFloat(coordMatch[2]);
    if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      return { name: trimmed, lat, lon };
    }
  }

  // Fall back to whatever lat/lon is currently set in the settings drawer,
  // paired with the typed name — lets users type a custom label after
  // setting coordinates manually.
  const latInput = parseFloat(document.getElementById("latInput").value);
  const lonInput = parseFloat(document.getElementById("lonInput").value);
  if (!Number.isNaN(latInput) && !Number.isNaN(lonInput)) {
    return { name: trimmed, lat: latInput, lon: lonInput };
  }
  return null;
}

// ---------- Settings drawer ----------
const menuBtn = document.getElementById("menuBtn");
const drawer = document.getElementById("settingsDrawer");
const drawerScrim = document.getElementById("drawerScrim");
const closeDrawer = document.getElementById("closeDrawer");

function openDrawer() {
  drawer.classList.remove("hidden");
  drawerScrim.classList.remove("hidden");
  drawer.setAttribute("aria-hidden", "false");
  menuBtn.setAttribute("aria-expanded", "true");
}
function hideDrawer() {
  drawer.classList.add("hidden");
  drawerScrim.classList.add("hidden");
  drawer.setAttribute("aria-hidden", "true");
  menuBtn.setAttribute("aria-expanded", "false");
}
menuBtn.addEventListener("click", openDrawer);
closeDrawer.addEventListener("click", hideDrawer);
drawerScrim.addEventListener("click", hideDrawer);

const demoToggle = document.getElementById("demoToggle");
const demoHint = document.getElementById("demoHint");
const scenarioRow = document.getElementById("scenarioRow");
const scenarioSelect = document.getElementById("scenarioSelect");

function syncDemoUI() {
  state.demoMode = demoToggle.checked;
  demoHint.textContent = state.demoMode
    ? "Using simulated data — ideal for a presentation."
    : "Fetching live data from weather, air-quality, and earthquake APIs.";
  scenarioRow.classList.toggle("hidden", !state.demoMode);
}
demoToggle.addEventListener("change", syncDemoUI);
scenarioSelect.addEventListener("change", () => { state.scenario = scenarioSelect.value; });
syncDemoUI();

document.getElementById("latInput").addEventListener("change", (e) => { state.lat = parseFloat(e.target.value); });
document.getElementById("lonInput").addEventListener("change", (e) => { state.lon = parseFloat(e.target.value); });

// ---------- Analyze ----------
const analyzeBtn = document.getElementById("analyzeBtn");
const locationInput = document.getElementById("locationInput");
const searchError = document.getElementById("searchError");

analyzeBtn.addEventListener("click", () => {
  const resolved = resolveLocation(locationInput.value);
  if (!resolved) {
    searchError.textContent = "Try a quick-select city, or type coordinates as \\"lat, lon\\".";
    searchError.classList.remove("hidden");
    return;
  }
  searchError.classList.add("hidden");
  state.locationName = resolved.name;
  state.lat = resolved.lat;
  state.lon = resolved.lon;
  document.getElementById("latInput").value = resolved.lat;
  document.getElementById("lonInput").value = resolved.lon;
  markActivePreset(resolved.name);
  runAnalysis();
});

locationInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") analyzeBtn.click();
});

async function runAnalysis() {
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing…";

  try {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: state.lat,
        longitude: state.lon,
        location_name: state.locationName,
        demo_mode: state.demoMode,
        scenario: state.scenario,
      }),
    });

    if (!res.ok) throw new Error(`Server responded ${res.status}`);
    const data = await res.json();

    if (data.status === "error") {
      renderError(data.error_message || "Analysis failed.");
      return;
    }

    renderEnvironment(data.environment || {});
    renderAlerts(data.alerts || []);
  } catch (err) {
    renderError(err.message || "Could not reach the SafeSphere API.");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
  }
}

// ---------- Rendering ----------
const statsSection = document.getElementById("statsSection");
const updatedAtEl = document.getElementById("updatedAt");

function renderEnvironment(env) {
  const aqi = env.aqi ?? "N/A";
  statsSection.innerHTML = `
    <div class="stat-card stat-card--temp">
      <div class="stat-card__icon">🌡️</div>
      <p class="stat-card__label">Temp</p>
      <p class="stat-card__value">${fmt(env.temperature_c, "°")}</p>
    </div>
    <div class="stat-card stat-card--wind">
      <div class="stat-card__icon">💨</div>
      <p class="stat-card__label">Wind</p>
      <p class="stat-card__value">${fmt(env.wind_speed_kmh)}<span style="font-size:1rem"> km/h</span></p>
    </div>
    <div class="stat-card stat-card--precip">
      <div class="stat-card__icon">🌧️</div>
      <p class="stat-card__label">Precip</p>
      <p class="stat-card__value">${fmt(env.precipitation_probability, "%")}</p>
    </div>
    <div class="stat-card stat-card--aqi">
      <div class="stat-card__icon">🫧</div>
      <p class="stat-card__label">AQI</p>
      <p class="stat-card__value">${aqi}</p>
    </div>
  `;
  updatedAtEl.textContent = env.updated_at ? `Last updated: ${env.updated_at}` : "";
}

function fmt(v, suffix = "") {
  if (v === undefined || v === null) return "N/A";
  const n = typeof v === "number" ? v : parseFloat(v);
  if (Number.isNaN(n)) return "N/A";
  return `${Math.round(n * 10) / 10}${suffix}`;
}

const alertsList = document.getElementById("alertsList");
const alertsSummary = document.getElementById("alertsSummary");

function severityClass(sev) {
  switch ((sev || "").toUpperCase()) {
    case "CRITICAL": return "alert-card--critical";
    case "HIGH": return "alert-card--high";
    case "MODERATE": return "alert-card--moderate";
    default: return "alert-card--low";
  }
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    alertsSummary.textContent = "No significant hazards detected.";
    alertsList.innerHTML = `<p class="alerts-empty">Conditions appear normal. This doesn't mean there's no risk — always stay informed.</p>`;
    return;
  }

  const sorted = [...alerts].sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0));
  alertsSummary.textContent = `${sorted.length} alert${sorted.length > 1 ? "s" : ""} requiring your attention`;

  alertsList.innerHTML = sorted.map(renderAlertCard).join("");
}

function renderAlertCard(alert) {
  const sev = (alert.severity || "LOW").toUpperCase();
  const breakdown = alert.priority_breakdown;
  const actions = alert.actions || [];
  const avoid = alert.avoid || [];

  return `
    <article class="alert-card ${severityClass(sev)}">
      <div class="alert-card__head">
        <span class="alert-card__badge">${sev}</span>
        <h3 class="alert-card__title">${escapeHtml(alert.title || "Safety Alert")}</h3>
        <span class="alert-card__score">${alert.priority_score ?? 0}/100</span>
      </div>

      <div class="alert-card__tags">
        ${alert.hazard_type ? `<span class="alert-card__tag">${escapeHtml(alert.hazard_type)}</span>` : ""}
        ${alert.source ? `<span class="alert-card__tag">${escapeHtml(alert.source)}</span>` : ""}
      </div>

      <p class="alert-card__summary">${escapeHtml(alert.summary || "No summary available.")}</p>

      <details>
        <summary>Why am I seeing this alert?</summary>
        <p>${escapeHtml(alert.why || "No explanation available.")}</p>
        ${breakdown ? `
          <ul class="priority-breakdown">
            ${(breakdown.factors || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("")}
          </ul>
          <p class="priority-breakdown__total">Total: ${breakdown.score ?? 0} points (${escapeHtml(breakdown.level || "UNKNOWN")})</p>
        ` : ""}
      </details>

      ${(actions.length || avoid.length) ? `
        <div class="action-columns">
          <div class="action-columns--do">
            <h4>Recommended actions</h4>
            <ul>${actions.map((a) => `<li>${escapeHtml(a)}</li>`).join("") || "<li>None listed.</li>"}</ul>
          </div>
          <div class="action-columns--avoid">
            <h4>Things to avoid</h4>
            <ul>${avoid.map((a) => `<li>${escapeHtml(a)}</li>`).join("") || "<li>None listed.</li>"}</ul>
          </div>
        </div>
      ` : ""}

      <details class="extra-details">
        <summary>Additional details</summary>
        <dl>
          ${alert.distance_km ? `<dt>Distance</dt><dd>${alert.distance_km} km</dd>` : ""}
          ${alert.location ? `<dt>Location</dt><dd>${escapeHtml(alert.location)}</dd>` : ""}
          <dt>Confidence</dt><dd>${Math.round((alert.confidence || 0) * 100)}%</dd>
          <dt>Timestamp</dt><dd>${escapeHtml(alert.timestamp || "N/A")}</dd>
        </dl>
      </details>
    </article>
  `;
}

function renderError(message) {
  alertsSummary.textContent = "";
  alertsList.innerHTML = `<p class="alerts-empty">Analysis failed: ${escapeHtml(message)}. Try again, or switch to demo mode in Settings.</p>`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Initial render — kick off a live analysis for the default location right
// away, so the dashboard shows real current conditions without waiting for
// the user to click Analyze first.
renderEnvironment({});
markActivePreset(state.locationName);
runAnalysis();

</script>
</body>
</html>
"""


# ----------------------------------------------------------------------
# HTTP server
# ----------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/health":
            self._send_json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/analyze":
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                req = {}
            latitude = req.get("latitude", 13.0827)
            longitude = req.get("longitude", 80.2707)
            location_name = req.get("location_name", "")
            demo_mode = req.get("demo_mode", False)

            if demo_mode:
                result = analyze_demo(
                    latitude, longitude, location_name, req.get("scenario", "normal")
                )
            else:
                try:
                    result = analyze_live(latitude, longitude, location_name)
                except Exception as error:  # noqa: BLE001 - never crash the server on a bad request
                    print(f"[SafeSphere] Live analysis failed: {error}")
                    result = {
                        "location": {"name": location_name, "latitude": latitude, "longitude": longitude},
                        "environment": {},
                        "alerts": [],
                        "status": "error",
                        "error_message": "Live analysis failed unexpectedly. Try demo mode instead.",
                        "is_demo_mode": False,
                    }
            self._send_json(result)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"SafeSphere demo running \u2014 open http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
