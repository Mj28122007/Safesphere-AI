# SafeSphere Product Brief

## Original problem statement
Integrate the existing SafeSphere UI/UX with backend functions from the public GitHub repository and make the experience substantially better. The requested improvements include functional buttons, a hover-expanded top-right menu, animated search with Enter-to-submit, all backend features represented in the frontend, demo data fallback, and a small financial graph inferred from the financial endpoint.

## Product and personas
- **Risk-aware traveler / resident:** wants a quick, understandable view of weather conditions and nearby hazards.
- **Operations analyst:** needs explainable alerts, risk status, and a compact financial disruption signal.
- **Demo presenter:** needs predictable scenarios and data when live sources are unavailable.

## Architecture decisions
- React frontend uses `REACT_APP_BACKEND_URL` for all API requests.
- FastAPI backend remains on the existing supervised port and wraps the GitHub hazard-analysis behavior through `/api/analyze`.
- MongoDB configuration remains protected and unchanged.
- Keyless Open-Meteo weather/air-quality sources are used for live telemetry; demo scenarios are deterministic.
- Financial intelligence is served by `/api/financial` until a real financial provider/endpoint is available.

## Core requirements (static)
- Location search by preset city or latitude/longitude coordinates.
- Enter key and Analyze button submit a new analysis.
- Live/demo telemetry with explicit fallback messaging.
- Normal, flood, earthquake, and cyclone scenario controls.
- Weather metrics, risk map, threat status, protocol action, safety alerts, and financial intelligence.
- Small financial projection graph, disruption alerts, and exposed entities.
- Responsive layout with usable mobile behavior.

## Implemented
### 2026-09-01
- Replaced starter screen with SafeSphere intelligence dashboard matching the UXpilot direction.
- Added FastAPI `/api/analyze` with coordinate validation, deterministic hazard scenarios, and live weather/air-quality telemetry.
- Added `/api/financial` response model and compact financial series for the frontend chart.
- Added animated search loading state, preset locations, Enter-to-submit, hover menu, live/demo refresh, scenario selector, protocol feedback, and user-facing fallback states.
- Added atmospheric telemetry cards, responsive risk mapping view, safety response queue, chart, disruption feed, and entity exposure list.
- Added unique `data-testid` attributes across interactive and critical UI flows.
- Verified build, backend regression, end-to-end interactions, and 390px mobile no-overflow.

## Prioritized backlog
### P0
- Replace deterministic financial data with the real financial intelligence endpoint when it exists.
- Add geocoding for arbitrary city names instead of relying on presets or manually entered coordinates.

### P1
- Add richer route mapping and emergency protocol execution once those backend functions are provided.
- Persist saved locations and alert history in MongoDB.
- Add alert acknowledgement and notification preferences.

### P2
- Add historical trend comparison and exportable risk reports.
- Add team workspaces and role-based analyst views.

## Next tasks
1. Connect the real financial backend contract and map its series into the existing chart.
2. Add city-name geocoding and recent-search suggestions.
3. Persist alert history and protocol acknowledgements.