"""
Telemetry ingestion layer.

Per docs/ARCHITECTURE.md ("Telemetry Ingestion Layer"), every source in this
package — the deterministic simulator (`telemetry_simulator.py`,
`scenarios.py`) and CSV upload (`csv_source.py`) — produces measurements in
one common shape (see `schemas.NormalizedMeasurement`). The rest of the
application (services, API, and the future Intelligence Core) consumes that
common shape and never needs to know which source a row came from.
"""
