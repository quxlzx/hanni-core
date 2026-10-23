# Supply an owner-reviewed CPU image containing Python, node/npm, opencode,
# aider-chat, gpt-researcher, langgraph and the required local research backend.
# Do not use a model-serving image or mount model weights.
ARG HARNESS_BASE_IMAGE
FROM ${HARNESS_BASE_IMAGE}
USER root
COPY pyproject.toml README.md /opt/hanni/
COPY src /opt/hanni/src
COPY deployment/cluster-harnesses/worker.py /opt/hanni/worker.py
# Install project source without downloads, model files or dependency changes.
RUN python -m pip install --no-deps /opt/hanni
USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["python", "/opt/hanni/worker.py"]
