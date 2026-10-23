# GPU selection

HANNI selects llama.cpp GPUs from the device list reported by the installed
llama.cpp binary. This keeps routing tied to the backend device IDs that will
actually be passed to `--device` and avoids Windows `AdapterRAM` limitations.
The policy is intended to work with AMD, NVIDIA, and supported Intel discrete
GPUs on Windows 11 without hard-coding Vulkan/CUDA device numbers.

## Automatic policy

The default automatic policy is `smallest_8gb`:

1. Enumerate llama.cpp devices and ignore known integrated/software adapters.
2. Treat a card reporting at least **7680 MiB** as an 8 GB-class GPU. Drivers
   often report an 8 GiB card slightly below 8192 MiB (for example 8176 MiB).
3. Among qualifying discrete GPUs, try the **smallest total VRAM first**.
4. The selected card must also have enough currently reported free VRAM for the
   model's configured `vram_budget_mb` plus HANNI's reserve.
5. If it does not fit, try the next-smallest qualifying GPU.
6. If no qualifying card can safely fit the model, fail clearly instead of
   silently choosing an unknown/shared-memory adapter.

Example:

| GPU | Reported VRAM | Model fits? | AUTO result |
| --- | ---: | --- | --- |
| RX 6600 XT | 8176 MiB | yes | selected |
| RX 9060 XT | 16304 MiB | yes | left free |
| RX 7900 XT | 20464 MiB | yes | left free |

If the current model requires more than the 6600 XT can safely hold, AUTO moves
to the 9060 XT, then the 7900 XT if necessary.

The automatic configuration is:

```yaml
gpu_selection: smallest_8gb
```

The legacy `most_vram` strategy remains supported for older profiles, and
`configured` still supports explicit `device_name_hints` profiles.

## Dashboard override

The **GRAPHICS** panel now includes **HANNI MODEL GPU**. It offers:

- **AUTO** — use the smallest usable 8 GB-class GPU according to the policy above.
- Any discrete GPU currently reported by llama.cpp — pin HANNI's primary model
  to that GPU.

The choice is persisted in `data/gpu-routing.json`. Manual choices store the
adapter name as well as its current backend device ID and capacity, so normal
Vulkan/CUDA renumbering after a reboot does not invalidate the choice when the
adapter name remains unique.

A loaded llama.cpp model cannot migrate between GPUs in place. Changing the
selector therefore changes the route for the **next model start**. The dashboard
shows when the running model is still on a different GPU and a restart is
required. HANNI does not terminate a running model just because the selector was
changed.

The dashboard override applies only to HANNI's configured **primary model**.
Other model profiles continue to follow their own GPU settings.

## Notes and limits

- AUTO is based on total/free VRAM reported by llama.cpp, not GPU utilization.
- Another application can allocate VRAM between discovery and model load; the
  actual llama.cpp launch can still fail in that race and should be retried.
- If two installed GPUs have exactly the same model name and capacity, backend
  device IDs may still be needed to distinguish them after hardware/driver
  re-enumeration.
- CPU-only model profiles do not probe or select a GPU.
