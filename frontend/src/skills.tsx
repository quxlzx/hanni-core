import { useRef, useState } from "react";
import { request, write } from "./api";
import { usePrivateResource } from "./feature_types";
import "./learning.css";

type Skill = { name: string; description: string; triggers: string[]; origin: string; state: string; pinned: boolean; revision: string; views: number; uses: number; patches: number };
type Draft = { name: string; description: string; instructions: string; triggers: string[]; expected_revision: string; verification: string; correction: string };
type Detail = { name: string; description: string; instructions: string; triggers: string[]; revision: string; history: { revision: string; verification: string; correction: string; created: string }[] };
type Proposal = { id: string; revision: string; data: Draft & { absorbs: { name: string; revision: string }[] }; diff: string; source: string };
type Memory = { id: string; content: string; updated_at: string; source_ref: string; kind: string };
type Run = { id: string; state: string; purpose: string; conversation: string; result: { message?: string } };
type Settings = { enabled: boolean; exchange_threshold: number; cooldown_seconds: number; curator_enabled: boolean; curator_interval_hours: number; stale_days: number; archive_days: number; consolidate: boolean; revision: string };
type Data = { available: boolean; reason: string | null; skills: Skill[]; proposals: Proposal[]; memories: Memory[]; runs: Run[]; settings: Settings };
type Journey = { items: { id: string; kind: string; text: string; action: string; created: number }[] };
type Batch = { id: string; tasks: { id: string; state: string }[] };
const tabs = ["Library", "Review", "Journey", "Learning settings", "Training data"] as const;
const emptyDraft: Draft = { name: "", description: "", instructions: "", triggers: [], expected_revision: "", verification: "", correction: "" };

export function SkillsPage({ token }: { token: string }) {
  const resource = usePrivateResource<Data>("/api/learning", token, 5000);
  const sessions = usePrivateResource<{ conversations: { id: string; title: string }[] }>("/api/chat/conversations", token, 30000);
  const journey = usePrivateResource<Journey>("/api/learning/journey", token, 10000);
  const batches = usePrivateResource<{ batches: Batch[] }>("/api/learning/batches", token, 5000);
  const [tab, setTab] = useState<(typeof tabs)[number]>("Library");
  const [query, setQuery] = useState(""), [showArchived, setShowArchived] = useState(false);
  const [conversation, setConversation] = useState(""), [focus, setFocus] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null), [draft, setDraft] = useState<Draft | null>(null);
  const [revising, setRevising] = useState<{ id: string; revision: string } | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [source, setSource] = useState<unknown>(null), [curation, setCuration] = useState<unknown>(null);
  const [prompts, setPrompts] = useState(""), [exportBatch, setExportBatch] = useState(""), [format, setFormat] = useState("trajectory");
  const [error, setError] = useState(""), [notice, setNotice] = useState(""), [busy, setBusy] = useState(false);
  const lock = useRef(false), pending = useRef<{ signature: string; id: string } | null>(null);
  const data = resource.data, blocked = busy || !token || !data?.available || Boolean(resource.error);
  const selectedConversation = conversation || sessions.data?.conversations[0]?.id || "default";
  const activeReview = data?.runs.some(run => run.state === "running");
  function refresh() { resource.refresh(); journey.refresh(); batches.refresh(); }
  async function act(operation: string, payload: unknown, after?: () => void) {
    if (blocked || lock.current) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    const signature = JSON.stringify({ operation, data: payload, token });
    const id = pending.current?.signature === signature ? pending.current.id : crypto.randomUUID();
    pending.current = { signature, id };
    try {
      const result = await write<{ message?: string }>("/api/learning", token, { id, operation, data: payload });
      pending.current = null; setNotice(result.message || "Change saved."); after?.();
      if (operation === "curator") setCuration(result);
    } catch (e) { setError(e instanceof Error ? e.message : "Learning action failed. Refresh and try again."); }
    finally { lock.current = false; setBusy(false); refresh(); }
  }
  async function inspect(name: string) {
    try { setDetail(await request<Detail>("/api/learning/skill?name=" + encodeURIComponent(name), { headers: { "X-Hanni-Token": token } })); setDraft(null); setRevising(null); setError(""); }
    catch (e) { setError(String(e)); }
  }
  async function inspectSource(value: string) {
    const id = value.startsWith("review:") ? value.split(":")[1] : value;
    try { setSource(await request("/api/learning/source?id=" + encodeURIComponent(id), { headers: { "X-Hanni-Token": token } })); }
    catch (e) { setError(String(e)); }
  }
  async function download() {
    if (blocked || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const result = await request<{ filename: string; content: string; count: number; message: string }>(`/api/learning/export?batch=${encodeURIComponent(exportBatch)}&format=${format}`, { headers: { "X-Hanni-Token": token } });
      if (!result.count) { setNotice("No finished trajectories are available yet."); return; }
      const url = URL.createObjectURL(new Blob([result.content], { type: "application/x-ndjson" }));
      const link = document.createElement("a"); link.href = url; link.download = result.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000); setNotice(result.message);
    } catch (e) { setError(String(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  const chosen = settings || data?.settings;
  return <section className="screen-section learning-page" aria-busy={busy}>
    <div className="section-title"><h2>Skills</h2><span>Procedures learned from work, matched when relevant</span></div>
    <div className="learning-tabs" role="tablist" aria-label="Skills and learning">{tabs.map(name => <button key={name} type="button" role="tab" id={`learning-tab-${tabs.indexOf(name)}`} aria-controls={`learning-panel-${tabs.indexOf(name)}`} aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onKeyDown={event => {
      const current = tabs.indexOf(name);
      const next = event.key === "ArrowRight" ? (current + 1) % tabs.length : event.key === "ArrowLeft" ? (current + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
      if (next >= 0) { event.preventDefault(); setTab(tabs[next]); document.getElementById(`learning-tab-${next}`)?.focus(); }
    }} onClick={() => setTab(name)}>{name}{name === "Review" && data ? ` (${data.proposals.length + data.memories.length})` : ""}</button>)}</div>
    {(error || resource.error || data?.reason) && <p role="alert" className="error-text">{error || resource.error || data?.reason}</p>}
    {notice && <p role="status">{notice}</p>}
    {!data && !resource.error && <p role="status">Loading skills and learning history…</p>}
    {tabs.map((name, index) => <div key={name} role="tabpanel" id={`learning-panel-${index}`} aria-labelledby={`learning-tab-${index}`} hidden={tab !== name} tabIndex={0}>
      {name === "Library" && <>
        <div className="learning-toolbar"><label>Find a skill<input type="search" value={query} onChange={e => setQuery(e.target.value)} /></label><label className="learning-check"><input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />Include archived</label><button disabled={blocked} onClick={() => { setDraft({ ...emptyDraft }); setDetail(null); setRevising(null); }}>Create skill</button></div>
        {data?.skills.filter(s => (showArchived || s.state !== "archived") && `${s.name} ${s.description}`.toLowerCase().includes(query.toLowerCase())).map(skill => <div className="learning-row" key={skill.name}>
          <div><button className="text-link" onClick={() => void inspect(skill.name)}><strong>{skill.name}</strong></button><p>{skill.description}</p><p className="subtle">{skill.origin} · {skill.state}{skill.pinned ? " · Pinned" : ""} · Applied {skill.uses || 0} · Viewed {skill.views || 0} · Patched {skill.patches || 0}</p></div>
          {skill.origin === "learned" && <div className="learning-actions"><button disabled={blocked} onClick={() => void act("skill.lifecycle", { name: skill.name, revision: skill.revision, action: skill.pinned ? "unpin" : "pin" })}>{skill.pinned ? "Unpin" : "Pin"}</button><button disabled={blocked} onClick={() => void act("skill.lifecycle", { name: skill.name, revision: skill.revision, action: skill.state === "archived" ? "restore" : "archive" })}>{skill.state === "archived" ? "Restore" : "Archive"}</button></div>}
        </div>)}
        {data && !data.skills.length && <p>No skills saved yet. Create a procedure or review a completed conversation.</p>}
        {detail && !draft && <div className="learning-inspector"><h3>{detail.name}</h3><pre>{detail.instructions}</pre><button disabled={blocked} onClick={() => setDraft({ name: detail.name, description: detail.description, instructions: detail.instructions, triggers: detail.triggers, expected_revision: detail.revision, verification: "", correction: "" })}>Edit procedure</button><button className="text-link" onClick={() => setDetail(null)}>Close procedure</button><details><summary>Revision history</summary>{detail.history.map((r, i) => <p key={i}><code>{r.revision.slice(0, 12)}</code> · {r.created}<br />{r.correction}<br />Evidence: {r.verification}</p>)}</details></div>}
        {draft && <form className="learning-editor" onSubmit={e => { e.preventDefault(); void act(revising ? "skill.revise" : "skill.stage", revising ? { proposal_id: revising.id, revision: revising.revision, payload: draft } : draft, () => { setDraft(null); setRevising(null); setDetail(null); setTab("Review"); }); }}><h3>{draft.expected_revision ? "Correct a procedure" : "Create a procedure"}</h3>
          <label>Skill name<input required pattern="[a-z0-9][a-z0-9-]{0,62}" disabled={Boolean(draft.expected_revision)} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
          <label>When to use it<input required maxLength={500} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
          <label>Trigger keywords (comma separated)<input required value={draft.triggers.join(",")} onChange={e => setDraft({ ...draft, triggers: e.target.value.split(",") })} /></label>
          <label htmlFor="learning-procedure">Working procedure, commands and pitfalls</label><textarea id="learning-procedure" required rows={10} maxLength={20000} value={draft.instructions} onChange={e => setDraft({ ...draft, instructions: e.target.value })} />
          <label htmlFor="learning-verification">Verification evidence</label><textarea id="learning-verification" required rows={2} maxLength={3000} value={draft.verification} onChange={e => setDraft({ ...draft, verification: e.target.value })} />
          <label>What changed or was learned<input required maxLength={3000} value={draft.correction} onChange={e => setDraft({ ...draft, correction: e.target.value })} /></label>
          <div className="learning-actions"><button type="submit" disabled={blocked}>Stage diff for review</button><button type="button" onClick={() => { setDraft(null); setRevising(null); }}>Cancel edit</button></div>
        </form>}
      </>}
      {name === "Review" && <>
        <h3>Review a conversation</h3><p>A separate model request reads a saved snapshot. You can continue chatting; proposals stay inactive until accepted.</p>
        <div className="learning-toolbar"><div className="learning-field"><label htmlFor="learning-conversation">Conversation</label><select id="learning-conversation" value={selectedConversation} onChange={e => setConversation(e.target.value)}>{sessions.data?.conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></div><label>Optional focus<input maxLength={500} value={focus} onChange={e => setFocus(e.target.value)} /></label><button disabled={blocked || activeReview} onClick={() => void act("refine", { conversation: selectedConversation, focus })}>Review snapshot</button></div>
        {data?.runs.slice(0, 5).map(run => <div className="learning-row" key={run.id}><div><strong>{run.purpose} · {run.state}</strong><p>{run.result.message || "Reviewing a separate snapshot…"}</p></div><div className="learning-actions"><button disabled={blocked} onClick={() => void inspectSource(run.id)}>Inspect snapshot</button>{run.state === "running" && <button disabled={blocked} onClick={() => void act("cancel", { review_id: run.id })}>Cancel review</button>}</div></div>)}
        <h3>Proposed skills</h3>{data && !data.proposals.length && <p className="subtle">No skill diffs awaiting review.</p>}
        {data?.proposals.map(p => <details className="learning-proposal" key={p.id}><summary>{p.data.name} · {p.data.correction}</summary><p>{p.data.description}</p><p>Evidence: {p.data.verification}</p><p className="subtle">Source: {p.source}</p>{(p.source.startsWith("review:") || p.source.startsWith("task:")) && <button disabled={blocked} onClick={() => void inspectSource(p.source)}>Inspect source snapshot</button>}<pre className="learning-diff">{p.diff}</pre>{p.data.absorbs.length > 0 && <p>Accepting also archives: {p.data.absorbs.map(s => s.name).join(", ")}. Original packages remain recoverable.</p>}<div className="learning-actions"><button disabled={blocked} onClick={() => void act("skill.review", { proposal_id: p.id, revision: p.revision, action: "accept" })}>Accept skill diff</button><button disabled={blocked} onClick={() => void act("skill.review", { proposal_id: p.id, revision: p.revision, action: "reject" })}>Reject skill diff</button><button disabled={blocked} onClick={() => { const { absorbs, ...edit } = p.data; void absorbs; setDraft(edit); setRevising({ id: p.id, revision: p.revision }); setTab("Library"); }}>Revise proposal</button></div></details>)}
        <h3>Proposed personal memory</h3><p className="subtle">Facts and preferences use persistent memory. Full conversations remain searchable through session_search.</p>
        {data && !data.memories.length && <p className="subtle">No memory suggestions awaiting review.</p>}
        {data?.memories.map(m => <MemoryReview key={m.id} memory={m} disabled={blocked} review={(action, content) => void act("memory.review", { suggestion_id: m.id, expected_updated_at: m.updated_at, action, edited_content: content })} inspect={() => void inspectSource(m.source_ref)} />)}
        {source !== null && <div className="learning-inspector"><h3>Review source snapshot</h3><button onClick={() => setSource(null)}>Close snapshot</button><pre>{JSON.stringify(source, null, 2)}</pre></div>}
      </>}
      {name === "Journey" && <><h3>Learning journey</h3><p>Saved skills, current memories and review outcomes. Model weights are unchanged.</p>{journey.error && <p role="alert">{journey.error}</p>}{journey.data?.items.map((item, i) => <div className="learning-row" key={`${item.kind}-${item.id}-${i}`}><div><p><strong>{item.kind} · {item.action}</strong> <time dateTime={new Date(item.created * 1000).toISOString()}>{new Date(item.created * 1000).toLocaleString()}</time></p><p>{item.text}</p></div></div>)}{journey.data && !journey.data.items.length && <p className="subtle">No learning history yet. Completed reviews and accepted changes will appear here.</p>}</>}
      {name === "Learning settings" && chosen && <>
        <h3>Background review</h3><p>Reviews use the selected inference provider. Its normal request costs and data handling apply. They never execute tools or change active conversations.</p>
        <form className="learning-editor" onSubmit={e => { e.preventDefault(); const { revision, ...values } = chosen; void act("configure", { settings: values, expected_revision: revision }, () => setSettings(null)); }}>
          <label className="learning-check"><input type="checkbox" checked={chosen.enabled} onChange={e => setSettings({ ...chosen, enabled: e.target.checked })} />Review completed exchanges automatically</label>
          <label>New exchanges before review<input type="number" min={1} max={100} required value={chosen.exchange_threshold} onChange={e => setSettings({ ...chosen, exchange_threshold: Number(e.target.value) })} /></label>
          <label>Minimum time between reviews (seconds)<input type="number" min={60} max={86400} required value={chosen.cooldown_seconds} onChange={e => setSettings({ ...chosen, cooldown_seconds: Number(e.target.value) })} /></label>
          <h3>Skill maintenance</h3><label className="learning-check"><input type="checkbox" checked={chosen.curator_enabled} onChange={e => setSettings({ ...chosen, curator_enabled: e.target.checked })} />Maintain unused learned skills while idle</label>
          <label>Maintenance interval (hours)<input type="number" min={1} max={8760} required value={chosen.curator_interval_hours} onChange={e => setSettings({ ...chosen, curator_interval_hours: Number(e.target.value) })} /></label>
          <label>Mark stale after unused days<input type="number" min={1} max={3650} required value={chosen.stale_days} onChange={e => setSettings({ ...chosen, stale_days: Number(e.target.value) })} /></label>
          <label>Archive after unused days<input type="number" min={2} max={3650} required value={chosen.archive_days} onChange={e => setSettings({ ...chosen, archive_days: Number(e.target.value) })} /></label>
          <label className="learning-check"><input type="checkbox" checked={chosen.consolidate} onChange={e => setSettings({ ...chosen, consolidate: e.target.checked })} />Also ask the model to propose maintenance and consolidation</label>
          <p className="subtle">Bundled, pinned and schedule-referenced skills are protected. Archived packages are retained and can be restored from Library. Model consolidation stays staged for review.</p>
          <button type="submit" disabled={blocked}>Save learning settings</button>
        </form><div className="learning-actions"><button disabled={blocked} onClick={() => void act("curator", { dry_run: true, consolidate: false })}>Preview maintenance</button><button disabled={blocked} onClick={() => void act("curator", { dry_run: false, consolidate: false })}>Run maintenance</button><button disabled={blocked || activeReview} onClick={() => void act("curator", { dry_run: false, consolidate: true })}>Propose skill consolidation</button></div>{curation !== null && <pre>{JSON.stringify(curation, null, 2)}</pre>}
      </>}
      {name === "Training data" && <>
        <h3>Collect agent trajectories</h3><p>Run up to 20 prompts with read-only tools. Each gets a separate context and receipts. These runs create data; they do not train the model.</p>
        <form className="learning-editor" onSubmit={e => { e.preventDefault(); void act("batch", { prompts: prompts.split("\n").map(p => p.trim()).filter(Boolean) }, () => setPrompts("")); }}><label>One prompt per line<textarea required rows={5} value={prompts} maxLength={60000} onChange={e => setPrompts(e.target.value)} /></label><button disabled={blocked} type="submit">Queue read-only batch</button></form>
        {batches.error && <p role="alert">{batches.error}</p>}{batches.data?.batches.map(batch => <div className="learning-row" key={batch.id}><div><strong>Batch {batch.id.slice(0, 12)}</strong><p>{batch.tasks.map(t => `${t.id.slice(0, 8)}: ${t.state}`).join(" · ")}</p></div><button disabled={blocked} onClick={() => void act("batch.cancel", { id: batch.id })}>Cancel batch</button></div>)}
        <h3>Export for review or training</h3><p>Exports contain private task and tool content with credential redaction. Inspect them before sharing. System prompts and separate reasoning fields are excluded; rewards remain unassigned.</p>
        <div className="learning-toolbar"><div className="learning-field"><label htmlFor="learning-export-source">Source</label><select id="learning-export-source" value={exportBatch} onChange={e => setExportBatch(e.target.value)}><option value="">Latest 50 finished tasks</option>{batches.data?.batches.map(b => <option key={b.id} value={b.id}>Batch {b.id.slice(0, 12)}</option>)}</select></div><div className="learning-field"><label htmlFor="learning-export-format">Format</label><select id="learning-export-format" value={format} onChange={e => setFormat(e.target.value)}><option value="trajectory">HANNI trajectory JSONL</option><option value="sharegpt">ShareGPT JSONL</option></select></div><button disabled={blocked} onClick={() => void download()}>Download trajectories</button></div>
        <p className="subtle">The offline Atropos adapter accepts reviewed rewards and a local tokenizer to create ScoredDataGroup records. It does not start a training service or perform on-policy reinforcement learning.</p>
      </>}
    </div>)}
  </section>;
}

function MemoryReview({ memory, disabled, review, inspect }: { memory: Memory; disabled: boolean; review: (action: string, content: string | null) => void; inspect: () => void }) {
  const [content, setContent] = useState(memory.content);
  return <div className="learning-memory"><label htmlFor={`learning-memory-${memory.id}`}>{memory.kind === "correct" ? "Proposed memory correction" : "Proposed fact or preference"}</label><textarea id={`learning-memory-${memory.id}`} rows={3} maxLength={1000} value={content} onChange={e => setContent(e.target.value)} /><div className="learning-actions"><button disabled={disabled || !content.trim()} onClick={() => review("approve", content)}>Accept memory</button><button disabled={disabled} onClick={() => review("reject", null)}>Reject memory</button><button disabled={disabled} onClick={inspect}>Inspect source</button></div></div>;
}
