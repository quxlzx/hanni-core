# Phase 1 + Phase 2 native screenshots

These are unchanged captures of the actual framed Windows application at
1440 by 900 physical pixels. The copies committed beside this report are
byte-identical to their original PNGs. They are not generated mockups.

Before is the existing five-screen native release in
`data/hanni-desktop-review/iteration-2/`. After is the independently reviewed
sixteen-screen workspace in `data/hanni-desktop-review/phase2-primary-cycle2/`.
Cycle 3 changes Mini startup readiness only; the main feature layouts are unchanged.
The review server uses disclosed synthetic telemetry/chat/provider fixtures but
genuine permission-gated local workspace stores. Separate live telemetry and
configured-model/controller captures are recorded in the final verification report.

## Home before

![Existing native Home](images/phase12-before-home.png)

## Home after

![Three-area workspace navigation and native Home](images/phase12-after-home.png)

## Cluster before

![Existing native Cluster](images/phase12-before-cluster.png)

## Cluster after

![Compact sortable cluster and selected-node details](images/phase12-after-cluster.png)

## New persistent Tasks screen

Tasks had no dedicated screen in the baseline; a before image would be misleading.

![Real persistent local tasks in the native workspace](images/phase12-after-tasks.png)

The original complete matrix retains all sixteen routes at 1920 by 1080,
1440 by 900, 1366 by 768 and 900 by 650. Independent observations and exact
weighted categories are in [cycle 2](phase-2-cycle-2.md); Mini's failed initial
frames remain preserved there for comparison with its later corrected review.

## Final Mini startup

This fresh 600 by 420 native frame precedes interactions. The startup readiness
defect is absent; the independent final review gives Mini 8.7.

![Corrected native Mini initial state](images/phase12-final-mini.png)

## Final real-controller reply

The configured local model answered the RAM question through the original
`process.top_memory` tool. This is a live controller capture, not the synthetic
reply used for layout/transport verification.

![Native Mini displaying the actual local-model RAM answer](images/phase12-live-controller-mini.png)

## Final live cluster

All eight active members have real SSH CPU/RAM readings. Yunjin is under repair
and unprobed. This 1440 by 900 capture is separate from the fixture comparison.

![Native Cluster showing actual eight-node resource samples](images/phase12-live-cluster.png)
