# OpsLens animation artifact

Run `python scripts/generate_opslens_animation.py` from the repository root. It regenerates the deterministic manifest and HTML reel by running the real API workflow against a temporary SQLite demo workspace.

For the accepted runtime evidence, run `python scripts/generate_real_runtime_video.py` and review [`REAL_RUNTIME.md`](REAL_RUNTIME.md). It preserves the actual API rows, forecast points, scenario assurance, and approval steps in CSV/JSON alongside the MP4.
