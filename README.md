# TerraSignal — Regional Market Intelligence

A dependency-free, responsive feature that starts with a source-fed list of recent disaster alerts. Users select an affected area and immediately see the likely market domains and companies with local exposure.

## Run it

Open `index.html` in a browser. No build step is required.

## Included behaviour

- Recent-disaster alert cards instead of manual event entry
- Affected market domains, confidence, and short-term forecast window
- Companies tied to regional headquarters or key local operations
- Visible event-source label and source-to-signal workflow
- Responsive desktop/mobile design

## Production integration

The demo fixture is `recentDisasters` at the top of `app.js`. Replace it from your backend with verified data from an appropriate disaster source, for example NDMA, IMD, GDACS, or ReliefWeb, plus a maintained company-location dataset. Preserve the source name, alert time, and disclaimer so users can judge freshness and provenance. This is decision support—not investment advice.
