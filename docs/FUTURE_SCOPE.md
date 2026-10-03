# Future Scope

Items intentionally kept out of the MVP, now that several previously-"future" items (realistic simulator, verification workflow, evidence layer, factor registry) have been pulled into the MVP itself per the revised plan — see `LIMITATION_RESOLUTION_MATRIX.md` for what moved in.

- **Real IoT/BMS integration** — smart electricity meters, water-flow sensors, building management systems feeding the same ingestion interface. No change to the Intelligence Core required.
- **ML-based anomaly detection upgrade** — once enough real multi-site historical data exists, evaluate seasonal decomposition or lightweight models alongside the existing statistical baseline, retained as an explainable fallback/sanity check rather than replaced outright.
- **Multi-tenant enterprise auth/RBAC** — organization-level roles, facility-manager vs. admin permissions, multiple organizations.
- **Portfolio rollups** — cross-location and cross-organization benchmarking for chains/campuses with multiple sites.
- **Fuel and waste resource types** — schema already supports this via a new enum value; not implemented until the electricity/water core is polished and stable, per explicit instruction.
- **Automated actions** — where safe and permitted (e.g., HVAC scheduling changes) rather than only human-executed recommendations, once trust in the detection/verification loop is established through real deployments.
- **Regulatory-grade emissions reporting** — Scope 1/2/3 alignment for organizations needing it for compliance/ESG reporting, building on the existing configurable emission-factor registry.
- **Mobile notifications** — push alerts to facility staff on high-severity anomalies rather than requiring a dashboard visit.
- **Sensor-drift / data-trust features** — stuck-value detection, missing-data repair, confidence bands on baselines.
