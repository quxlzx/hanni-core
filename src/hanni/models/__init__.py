"""Local model clients, registry, and resource monitoring (Milestone 1)."""

from hanni.models.client import LlamaCppClient, ModelClientError, ModelHealth, ModelProtocolError, ModelUnavailableError
from hanni.models.registry import create_client, model_spec
from hanni.models.resource_manager import GpuSnapshot, ResourceSnapshot, snapshot_resources

__all__ = [
    "GpuSnapshot",
    "LlamaCppClient",
    "ModelClientError",
    "ModelHealth",
    "ModelProtocolError",
    "ModelUnavailableError",
    "ResourceSnapshot",
    "create_client",
    "model_spec",
    "snapshot_resources",
]
