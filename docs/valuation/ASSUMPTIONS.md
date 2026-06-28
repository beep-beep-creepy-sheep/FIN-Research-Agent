# Valuation Assumptions

Valuation assumptions are explicit inputs, not facts.

Each assumption set includes:

- Symbol, model type, and scenario.
- Revenue growth, FCF margin, discount rate, terminal growth, projection years.
- Optional tax rate, capex intensity, working-capital intensity, and peer multiple.
- Source, creator, version, and deterministic hash.

Changing assumptions changes the valuation run ID. Unsafe assumptions return validation errors instead of silently clamping results.
