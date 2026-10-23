export type PerformanceSample = {
  sampled_at: number;
  latency_ms: number | null;
  ttft_ms: number | null;
  generation_tps: number | null;
  prompt_tps: number | null;
  queue_ms: number | null;
  error: boolean;
};

export type EndpointPerformance = {
  sample_count: number;
  recent_failures: number;
  window_seconds: number;
  last_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  ttft_ms: number | null;
  generation_tps: number | null;
  prompt_tps: number | null;
  queue_ms: number | null;
  history: PerformanceSample[];
};

export type GpuMeasurement = {
  vram_total_bytes: number | null;
  vram_free_bytes: number | null;
  utilization_percent: number | null;
};

const measured = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
const seconds = (value: number | null | undefined) =>
  measured(value) ? `${(value! / 1000).toFixed(2)} s` : "Not measured";
const tokens = (value: number | null | undefined) =>
  measured(value) ? `${value!.toFixed(1)} tokens/s` : "Not measured";
const age = (value: number | null | undefined) => {
  if (!measured(value) || value === 0) return "Not measured";
  const elapsed = (Date.now() - value! * 1000) / 1000;
  if (elapsed < 0 || !Number.isFinite(elapsed)) return "Not measured";
  if (elapsed < 60) return `${Math.floor(elapsed)} s ago`;
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)} min ago`;
  return `${Math.floor(elapsed / 3600)} h ago`;
};

function LatencyHistory({ history }: { history: PerformanceSample[] }) {
  const samples = history.slice(-32);
  const known = samples.filter((sample) => measured(sample.latency_ms));
  if (known.length < 2)
    return (
      <p className="routing-history-empty">
        History appears after two recorded response times.
      </p>
    );
  const width = 440;
  const height = 64;
  const maximum = Math.max(1, ...known.map((sample) => sample.latency_ms!));
  const position = (sample: PerformanceSample, index: number) => ({
    x: 2 + (index / (samples.length - 1)) * (width - 4),
    y: height - 2 - (sample.latency_ms! / maximum) * (height - 4),
  });
  let continuous = false;
  const path = samples
    .map((sample, index) => {
      if (!measured(sample.latency_ms)) {
        continuous = false;
        return "";
      }
      const { x, y } = position(sample, index);
      const command = continuous ? "L" : "M";
      continuous = true;
      return `${command} ${x},${y}`;
    })
    .join(" ");
  return (
    <figure className="routing-latency-history">
      <figcaption>
        <span>Response history · sample order</span>
        <span>
          Last {samples.length} measurements · 0–{seconds(maximum)}
        </span>
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Response latency in recorded sample order across ${samples.length} samples, latest ${seconds(samples.at(-1)?.latency_ms)}, maximum ${seconds(maximum)}. Gaps are unmeasured timings; marked points are failures.`}
      >
        <path
          className="routing-history-baseline"
          d={`M 2 ${height - 2} H ${width - 2}`}
        />
        <path className="routing-history-line" d={path} />
        {samples.map(
          (sample, index) =>
            measured(sample.latency_ms) && (
              <circle
                key={index}
                className={
                  sample.error
                    ? "routing-history-failure"
                    : "routing-history-sample"
                }
                {...{
                  cx: position(sample, index).x,
                  cy: position(sample, index).y,
                  r: sample.error ? 3 : 1.5,
                }}
              >
                <title>
                  {sample.error ? "Failed response" : "Response"} ·{" "}
                  {seconds(sample.latency_ms)}
                </title>
              </circle>
            ),
        )}
      </svg>
    </figure>
  );
}

export function ModelPerformance({
  performance,
  gpu,
  health,
  resourceSampledAt,
  stale = false,
}: {
  performance?: EndpointPerformance;
  gpu?: GpuMeasurement | null;
  health: string;
  resourceSampledAt?: number | null;
  stale?: boolean;
}) {
  const used =
    measured(gpu?.vram_total_bytes) &&
    measured(gpu?.vram_free_bytes) &&
    gpu!.vram_free_bytes! <= gpu!.vram_total_bytes!
      ? gpu!.vram_total_bytes! - gpu!.vram_free_bytes!
      : null;
  const gpuMemory =
    used == null
      ? "Not measured"
      : `${(used / 1024 ** 3).toFixed(2)} / ${(gpu!.vram_total_bytes! / 1024 ** 3).toFixed(2)} GiB`;
  const samples = performance?.sample_count ?? 0;
  return (
    <div className="routing-performance" aria-label="Endpoint performance">
      <dl className="routing-performance-readings">
        <div>
          <dt>Response P50 / P95</dt>
          <dd>
            {seconds(performance?.p50_latency_ms)} /{" "}
            {seconds(performance?.p95_latency_ms)}
          </dd>
        </div>
        <div>
          <dt>First visible token</dt>
          <dd>{seconds(performance?.ttft_ms)}</dd>
        </div>
        <div>
          <dt>Generation</dt>
          <dd>{tokens(performance?.generation_tps)}</dd>
        </div>
        <div>
          <dt>Prompt processing</dt>
          <dd>{tokens(performance?.prompt_tps)}</dd>
        </div>
        <div>
          <dt>HANNI queue wait</dt>
          <dd>{seconds(performance?.queue_ms)}</dd>
        </div>
        <div>
          <dt>GPU memory used / total</dt>
          <dd>{gpuMemory}</dd>
        </div>
      </dl>
      <div className="routing-performance-footer">
        <span>
          {samples
            ? `${samples} measurements in the last ${Math.round((performance?.window_seconds ?? 3600) / 60)} minutes`
            : "No recent performance measurements"}
        </span>
        <span>
          Last response sample: {age(performance?.history.at(-1)?.sampled_at)}
        </span>
        <span className={performance?.recent_failures ? "warning" : ""}>
          {samples
            ? `${performance?.recent_failures ?? 0} recent failures`
            : "Failures not measured"}
        </span>
        <span>
          GPU utilization:{" "}
          {measured(gpu?.utilization_percent) &&
          gpu!.utilization_percent! <= 100
            ? `${gpu!.utilization_percent!.toFixed(0)}%`
            : "Not measured"}
        </span>
      </div>
      {samples > 0 && <LatencyHistory history={performance?.history ?? []} />}
      <p className="routing-performance-note">
        {stale
          ? "Displayed performance may be stale; refresh failed"
          : health === "healthy"
            ? "Recorded samples"
            : "Historical samples; endpoint health is not current"}
        . First token is client-observed; processing rates are server-reported.
        Readings use the most recent measured value. GPU sample age:{" "}
        {age(resourceSampledAt)}.
      </p>
    </div>
  );
}
