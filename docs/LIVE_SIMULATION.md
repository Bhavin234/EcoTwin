# EcoTwin Live Simulated Telemetry

EcoTwin includes an optional live-demo telemetry stream.

It advances a **simulated clock** while the Data page is open. Every tick
appends deterministic electricity and water readings through the same
normalized measurement table used by the existing simulator/CSV ingestion.

## Important architecture rule

This is mock telemetry, not physical sensor data. The simulator does not ask
AI to invent measurements.

- Simulator: generates deterministic telemetry.
- PostgreSQL/SQLite: persists telemetry and application state.
- Deterministic analytics: owns anomaly/baseline/impact numbers.
- Anthropic: optional contextual reasoning only.

## How it works

The Data page can start a live stream. While running, the browser calls:

`POST /api/data/live/tick`

every 10 seconds.

Each call advances the simulated clock by 1, 6, or 24 hours and persists the
new readings.

The default 6-hour speed makes the demo visually useful without waiting for
real wall-clock hours.

The simulator includes a deterministic weekday after-hours water-consumption
pattern so the existing analytics engine can discover a leak-like anomaly from
the telemetry rather than receiving an anomaly flag from the simulator.

The stream runs only while the browser page is open. It intentionally does
not rely on an in-process server scheduler, because free hosting platforms
may sleep or restart application instances.

For a production IoT integration, a real smart meter/BMS/IoT source would
write the same normalized telemetry contract instead.
