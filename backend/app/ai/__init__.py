"""
AI Reasoning Layer (docs/AI_ARCHITECTURE.md).

Everything in this package reasons over evidence that `app.analytics`
already computed — it never computes a number, a severity, a confidence
score, or a candidate-cause rating itself. If the AI is unavailable, times
out, or returns output that doesn't pass grounding validation, the pipeline
falls back to a deterministic investigation engine (`fallback.py`) that
produces an equivalent structural result from the same evidence.
"""
