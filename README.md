# Risk Intelligence — Updated Full-Screen Website

## Files

- `index.html` — complete runnable single-window website
- `config.js` — optional public Mapbox token configuration
- `config.example.js` — safe template for the configuration

## Run

Keep all three files in the same folder, then run:

```bash
python -m http.server 8000
```

Open `http://localhost:8000`.

## Search fix

- Click the location text to automatically select the full previous value.
- Type a new place and press **Analyse ✦** or Enter.
- Click **×** to permanently clear the saved Navi Mumbai/demo destination. The empty map state appears after the refresh.
- The app stores the selected location in the browser only under `riskDemoProfile`.

## Included changes

- No top bar or side navigation; the entire browser is an interactive map.
- Centered in-map search bar.
- Smooth green → yellow → orange → red heatmap gradient.
- Legible matching gradient legend and thresholds.
- Slide-in/out risk information panel.
- Circular score visualization with a color-filled conic percentage ring.
- Large Locate Me control using browser GPS permission.
- Mapped route from current GPS location (or selected zone) to the nearest lower-risk simulated zone.
- Cute rounded buttons and responsive mobile styling.
- Emergency-mode report flow stored in browser demo storage.

## Optional API key

For Mapbox geocoding, place your own **public** Mapbox token in `config.js`:

```js
window.RISK_CONFIG = {
  MAPBOX_PUBLIC_TOKEN: "pk.YOUR_PUBLIC_TOKEN"
};
```

Never include Mapbox secret tokens, database passwords, or server-side credentials in frontend code. With no Mapbox token, the demo uses Nominatim for location lookup and OSRM as an attempted demo routing provider.

## Disclaimer

Risk zones, risk scores, heatmaps, incidents, alerts, recommendations, and safe zones are deterministic simulated hackathon data. They do not represent verified real-time public-safety, crowd, health, or authority data.
