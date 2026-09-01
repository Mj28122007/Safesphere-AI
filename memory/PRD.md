# SafeSphere AI — PRD

## Problem
Integrate existing SafeSphere AI backend into a polished, responsive dashboard with 4 intelligence windows: Weather, Live Risk Map (iframe), Financial Intelligence, Emergency Response — with a live rotating NASA Earth video, rounded UI, large typography.

## Users
Analysts and operators monitoring weather-driven risk to operations, logistics and portfolios.

## Core (locked)
- Live weather (Open-Meteo, with deterministic fallback)
- Live risk map embedded as iframe from https://safesphereai-rudt.vercel.app/
- Financial intelligence with alerts + companies breakdown
- Emergency response desk block
- NASA SVS Earth mp4 hero visual

## Implemented (Feb 2026)
- Frontend 4-window grid (`/app/frontend/src/App.js`)
- NASA Earth video hero (video.spinning-earth)
- Enlarged weather typography (110px main / 46px stats)
- Redesigned Financial Intelligence (reference-alerts + reference-companies + storm/sun badge icons)
- iframe embed for SafeSphere live risk map
- Emergency response subwindow
- Backend endpoints: `POST /api/analyze`, `GET /api/financial`, `GET /api/weather`
- Fix: neutralised `[data-ve-dynamic]` visual-editor wrappers so dynamic numbers keep parent typography

## Backlog
### P1
- Geocoding + recent-city suggestions for weather search
- Break App.js monolith into `components/{Weather,Map,Finance,Emergency}.jsx`
### P2
- Persist alert history + protocol acknowledgements (MongoDB)
- Connect real financial backend contract and map series into finance window
- Storm/sun badges → lucide `CloudLightning` / `Sun` instead of unicode chars

## Health
- Broken: none
- Mocked: hazard scenarios, financial series, weather fallback (by design)
