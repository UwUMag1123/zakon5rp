Loader expects: codex.json, law.json, appeal.json, other.json at repo root (already present).
Fallback: docs.json (full 76 docs).

If index still has data/ paths, change line:
var parts = ['codex.json','law.json','appeal.json','other.json'];
