ARG NGC_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:<choose-current-arm64-dgx-spark-compatible-tag>
FROM ${NGC_PYTORCH_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs curl ca-certificates build-essential cmake pkg-config \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir \
    numpy scipy opencv-python-headless pydantic fastapi uvicorn rich \
    polars pyarrow matplotlib onnx \
    || (echo "Python package install failed. Check aarch64 wheel availability for the selected base image." >&2; exit 1)

# onnxruntime wheels are not always published for every aarch64 CUDA/Python combination.
RUN python3 -m pip install --no-cache-dir onnxruntime \
    || echo "WARNING: onnxruntime unavailable for this aarch64 base image; install a compatible wheel manually if needed."

WORKDIR /workspaces/aris
CMD ["bash"]
