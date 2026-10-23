// Saved operator notes from the verified migration; not live runtime evidence.
export const modelOperations: Record<string, {
  saved: string; service?: string; container?: string; account: string;
  runtime: string; auth: string; rollback?: string;
}> = {
  "nex-n2-mini": {saved: "2026-10-12", service: "hanni-nex.service", container: "hanni-model-nex",
    account: "athena@hanni", runtime: "Docker through user systemd",
    auth: "HANNI manages Control Center authentication; host-local model endpoint",
    rollback: "python3 ~/hanni-control/docker-migration/hanni_migrate_v3.py rollback nex"},
  "mellum-2.1": {saved: "2026-10-12", service: "hanni-mellum.service", container: "hanni-model-mellum",
    account: "athena@hanni", runtime: "Docker through user systemd",
    auth: "HANNI manages Control Center authentication; host-local model endpoint",
    rollback: "python3 ~/hanni-control/docker-migration/hanni_migrate_v3.py rollback mellum"},
  "swift-1.5": {saved: "2026-10-12", service: "hanni-swift.service", container: "hanni-model-swift",
    account: "athena@hanni", runtime: "Docker through user systemd; RX 9060 XT mapped to Vulkan0 in container",
    auth: "HANNI manages Control Center authentication; host-local model endpoint",
    rollback: "python3 ~/hanni-control/docker-migration/hanni_migrate_v3.py rollback swift"},
  "flash-next": {saved: "2026-10-12", account: "wonyoung@wonyoung",
    runtime: "Native Strata; Docker migration pending administrator installation",
    auth: "Strata API key stays in the existing protected configuration; HANNI handles authentication"},
};
