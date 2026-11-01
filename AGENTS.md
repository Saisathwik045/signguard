# SignGuard contributor guidance
Work on feature branches and preserve existing changes. Run `ruff check .` and `pytest -q`
in the cloud environment before committing. Never commit private keys, user uploads, or real
signed documents. Generate synthetic fixtures at runtime. Keep certificate trust, mathematical
signature validity, and heuristic visual evidence separate. Do not describe ELA/ORB scores as
forgery probabilities. Network fetching during certificate validation is disabled by default.
