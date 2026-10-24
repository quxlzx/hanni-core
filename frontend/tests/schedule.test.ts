import assert from "node:assert/strict";
import test from "node:test";
import { repeatLabel } from "../src/schedule_fields.ts";
const base = { cadence: "daily" as "daily" | "weekly" | "interval", at_time: "09:00", timezone: "America/Chicago", weekday: 0, interval_seconds: 3600 };
test("calendar schedules expose their wall time, timezone and weekday", () => {
  assert.equal(repeatLabel(base), "Daily at 09:00 · America/Chicago");
  assert.equal(repeatLabel({ ...base, cadence: "weekly", weekday: 4 }), "Every Friday at 09:00 · America/Chicago");
});
test("intervals are described without rounding or hiding their cadence", () => {
  assert.equal(repeatLabel({ ...base, cadence: "interval" }), "Every 1 hour(s)");
  assert.equal(repeatLabel({ ...base, cadence: "interval", interval_seconds: 90 }), "Every 1.5 minute(s)");
  assert.equal(repeatLabel({ ...base, cadence: "interval", interval_seconds: 172800 }), "Every 2 day(s)");
});
