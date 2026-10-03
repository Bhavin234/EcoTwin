# Emission Calculations (Revised)

## Approach

CO2e figures are estimates derived from a **configurable emission-factor registry** (the `emission_factors` table in `DATA_MODEL.md`), never hardcoded inline in application code. This is stated in the UI (Impact page footnote) and here.

```text
co2e_kg = consumption_in_unit × emission_factor(resource_type, version, effective_date)
```

## Registry fields (per limitation-resolution requirement)

Each factor row stores: `factor_value`, `unit`, `resource_type`, `source` (citation), `version`, `effective_from`. Changing a factor creates a new versioned row rather than mutating history, so past impact records remain traceable to the factor version that was actually used (`impact_records` reference the factor indirectly via the resource's `emission_factor_id` at calculation time — implementation should snapshot the factor value used onto the `impact_records` row, not just the FK, so historical figures don't silently change if the registry is later updated).

## Electricity

Standard grid emission factor (kg CO2e per kWh); default seed value should cite a documented public source (e.g., India's Central Electricity Authority CO2 Baseline Database or equivalent) — the exact figure and citation to be finalized and sourced during implementation, not assumed.

## Water

Water doesn't directly emit CO2e at point of use; EcoTwin converts water wastage into an indicative CO2e figure via a configurable "embedded energy per litre" factor (pumping/treatment/heating), clearly labeled in the UI as an *indirect/embedded* estimate, never merged with direct electricity figures into one undifferentiated number.

## What EcoTwin will not claim

- Not a verified, audited, regulatory-grade figure.
- Never silently changes a past figure when a factor is updated (see versioning above).
- Always shows which factor version/source produced a given number, on request (e.g., an info icon on the Impact page).

## Implementation notes (Milestone 3)

Default factors are seeded idempotently (`app/services/factor_service.py`, `ensure_default_factors`) the first time they're needed, rather than requiring a manual migration step:

- **Electricity:** 0.716 kg CO2e/kWh — modeled on India's CEA CO2 Baseline Database grid emission factor. The `source` field on the seeded row is explicit that this is an **illustrative default** and the exact figure/version should be verified and re-cited before any non-demo use.
- **Water:** 0.00035 kg CO2e/L — an illustrative embedded pumping/treatment energy proxy, similarly labeled.
- **Cost:** ₹8.00/kWh and ₹0.05/L (≈₹50/kL) — illustrative Indian commercial tariffs.

`GET /api/config/factors` returns the active factors (seeding defaults on first call); `PUT /api/config/factors/{cost|emission}/{id}` updates them — see `API.md`. `calculate_cost()` and `calculate_co2e()` (`app/analytics/calculations.py`) always take a factor object as an argument; no calculation function reads a hardcoded number.

## Factor snapshotting (Milestone 5)

Deferred by Milestone 3, now implemented: every `ImpactRecord` (estimated or verified) stores the emission factor's `factor_value`, `version`, and `source`, and the cost factor's `rate` and `currency`, exactly as they were at calculation time — not just a foreign key to the live registry row. Editing a factor later via `PUT /api/config/factors/emission/{id}` (or `cost/{id}`) only affects *future* calculations; every historical `ImpactRecord` remains reproducible and accurate to what was actually used, per this document's earlier commitment: "does not silently change a past figure when a factor is updated."
