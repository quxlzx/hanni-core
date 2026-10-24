"""Default local Windows tool registry.

Milestone 6 established the registry and its permission boundary. M9.2 through M9.4 widen the registered capability surface without changing that boundary:
every capability below is still validated, permission-checked,
confirmation-gated, emergency-stoppable, and audited by the same code paths.
"""

from __future__ import annotations

from pathlib import Path

from hanni.config.schema import AppConfig
from hanni.core.shutdown import EmergencyStop, FileStopStateStore
from hanni.tools.audit import ToolAuditLog
from hanni.tools.base import ToolContext, ToolRegistry
from hanni.reliability import get_service
from hanni.tools import apps as app_tools
from hanni.tools import todos as todo_tools
from hanni.tools import reminders as reminder_tools
from hanni.tools import workplace as workplace_tools
from hanni.tools import google_access as google_tools
from hanni.tools import email_tools
from hanni.tools import google_services
from hanni.tools import compute as compute_tools
from hanni.tools import cluster_harnesses as cluster_harness_tools
from hanni.tools import content as content_tools
from hanni.tools import devices as device_tools
from hanni.tools import devtools as dev_tools
from hanni.tools import diagnostics as diagnostic_tools
from hanni.tools import envtools as env_tools
from hanni.tools import files as file_tools
from hanni.tools import insight as insight_tools
from hanni.tools import media as media_tools
from hanni.tools import net as net_tools
from hanni.tools import notes as note_tools
from hanni.tools import overview as overview_tools
from hanni.tools import power as power_tools
from hanni.tools import powershell as powershell_tools
from hanni.tools import projects as project_tools
from hanni.tools import security as security_tools
from hanni.tools import spotify as spotify_tools
from hanni.tools import storage as storage_tools
from hanni.tools import system as system_tools
from hanni.tools import timekeep as time_tools
from hanni.tools import uiextra as ui_extra_tools
from hanni.tools import windows as windows_tools


def build_default_registry(config: AppConfig, *, data_dir: Path | None = None) -> ToolRegistry:
    root = Path(data_dir or config.paths.data_dir)
    stop = EmergencyStop(FileStopStateStore.for_data_dir(root))
    context = ToolContext(config.permissions, stop, ToolAuditLog(root), config.hanni.user.timezone,
                          reliability=get_service(root))
    registry = ToolRegistry(context)
    holder = diagnostic_tools.RegistryHolder()
    google_access = google_tools.GoogleAccess(timezone_name=config.hanni.user.timezone)
    registry.google_access = google_access
    for definition in (
        *system_tools.definitions(),
        *windows_tools.definitions(),
        *file_tools.definitions(),
        *powershell_tools.definitions(),
        *project_tools.definitions(),
        *net_tools.definitions(),
        *storage_tools.definitions(),
        *app_tools.definitions(),
        *media_tools.definitions(),
        *spotify_tools.definitions(),
        *content_tools.definitions(),
        *time_tools.definitions(registry),
        *dev_tools.definitions(),
        *compute_tools.definitions(),
        *cluster_harness_tools.definitions(config,data_dir=root),
        *insight_tools.definitions(),
        *power_tools.definitions(),
        *security_tools.definitions(),
        *device_tools.definitions(),
        *env_tools.definitions(),
        *ui_extra_tools.definitions(),
        *overview_tools.definitions(),
        *note_tools.definitions(root),
        *todo_tools.definitions(root),
        *reminder_tools.definitions(root),
        *workplace_tools.definitions(config),
        *google_tools.definitions(google_access),
        *email_tools.definitions(google_access),
        *google_services.definitions(google_access),
        *diagnostic_tools.definitions(config, holder),
    ):
        registry.register(definition)
    # Self-introspection describes the finished registry, never a partial one.
    holder.registry = registry
    if (root / 'cluster-harnesses/deployment.json').exists():
        from hanni.compute.harnesses import SandboxJobs
        jobs = SandboxJobs(root)
        def stop_sandbox_jobs(change, record):
            if change == 'tripped':
                # Local revocation precedes asynchronous bounded owned-job
                # cancellation, keeping emergency-stop interaction responsive.
                with jobs._connect() as db: db.execute('DELETE FROM leases')
                import threading
                threading.Thread(target=jobs.stop_all, daemon=True, name='hanni-sandbox-stop').start()
        stop.add_listener(stop_sandbox_jobs)
    return registry
