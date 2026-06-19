# AI Layer

The AI layer is for:

- Semantic indexing.
- Map annotation.
- Change detection review.
- Event explanation.
- Log analysis.

The AI layer must not be used for real-time control. It has no authority over steering, throttle, or brake.

Use the AI container after selecting a current NGC PyTorch image and authenticating:

```bash
docker login nvcr.io
just ai-shell
```

Models and caches must live under `ARIS_MODELS`.
