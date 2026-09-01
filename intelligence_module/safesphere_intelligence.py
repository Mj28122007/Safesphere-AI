"""SafeSphere AI - Main Module"""
from datetime import datetime
from services.weather_api import get_weather_simple
from services.air_quality_api import get_air_quality_simple
from services.earthquake_api import get_nearby_earthquakes_simple
from intelligence.hazard_detector import detect_all_hazards
from intelligence.alert_filter import filter_alerts_simple
from intelligence.alert_priority import prioritize_alerts
from intelligence.alert_deduplicator import deduplicate_alerts_simple
from intelligence.alert_personalizer import personalize_multiple_alerts
from utils.demo_alerts import get_demo_analysis

def get_dashboard_environment(latitude, longitude):
    """Get environmental data for dashboard"""
    weather = get_weather_simple(latitude, longitude)
    aq = get_air_quality_simple(latitude, longitude)
    
    return {"location": {"latitude": latitude, "longitude": longitude},
            "temperature_c": weather.get("temperature_c", 0),
            "precipitation_mm": weather.get("precipitation_mm", 0),
            "precipitation_probability": weather.get("precipitation_probability", 0),
            "wind_speed_kmh": weather.get("wind_speed_kmh", 0),
            "aqi": aq.get("aqi"),
            "pm2_5": aq.get("pm2_5"),
            "pm10": aq.get("pm10"),
            "updated_at": datetime.utcnow().isoformat() + "Z"}

def analyze_location(latitude, longitude, location_name="", gemini_api_key=None, clear_cache=True):
    """Master function - analyze location and generate alerts"""
    result = {"location": {"name": location_name, "latitude": latitude, "longitude": longitude},
              "environment": {}, "alerts": [], "status": "success", "error_message": None, "is_demo_mode": False}
    
    try:
        weather = get_weather_simple(latitude, longitude)
        aq = get_air_quality_simple(latitude, longitude)
        earthquakes = get_nearby_earthquakes_simple(latitude, longitude)
        
        result["environment"] = {"temperature_c": weather.get("temperature_c", 0),
                                  "precipitation_mm": weather.get("precipitation_mm", 0),
                                  "precipitation_probability": weather.get("precipitation_probability", 0),
                                  "wind_speed_kmh": weather.get("wind_speed_kmh", 0),
                                  "aqi": aq.get("aqi"),
                                  "pm2_5": aq.get("pm2_5"),
                                  "pm10": aq.get("pm10"),
                                  "updated_at": datetime.utcnow().isoformat() + "Z"}
        
        hazards = detect_all_hazards(weather if not weather.get("error") else None, earthquakes)
        filtered = filter_alerts_simple(hazards)
        prioritized = prioritize_alerts(filtered)
        deduplicated = deduplicate_alerts_simple(prioritized)
        alerts = personalize_multiple_alerts(deduplicated, location_name, gemini_api_key)
        
        result["alerts"] = alerts
        result["status"] = "success"
        
    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)
    
    return result

def analyze_location_demo(latitude, longitude, location_name="", scenario="normal"):
    """Demo version with simulated data"""
    return get_demo_analysis(latitude, longitude, location_name, scenario)

__all__ = ['analyze_location', 'analyze_location_demo', 'get_dashboard_environment']
