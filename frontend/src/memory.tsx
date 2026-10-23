import { useEffect, useRef, useState, type ReactNode } from "react";
import { write } from "./api";
import { usePrivateResource, storeInspection } from "./feature_types";
import { FeatureDialog } from "./feature_ui";
import {
  currentMemory,
  correctionData,
  reviewData,
  suggestionApplyAllowed,
  MemoryRequestLedger,
  type MemoryRecord,
  type MemorySuggestion,
  type MemoryExplorerData,
  type MemoryDetailData,
  type MemorySuggestionsData,
  type ProjectContextData,
  type MemoryProject,
} from "./memory_types";
import type { Screen } from "./types";
import "./memory.css";

const date = (value?: string) =>
  value
    ? new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Not recorded";
const words = (value: string) => value.replaceAll("_", " ");
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="memory-empty">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
function Loading() {
  return (
    <div className="skeleton-group" role="status" aria-label="Loading memory">
      <span className="skeleton" />
      <span className="skeleton medium" />
      <span className="skeleton short" />
    </div>
  );
}
type Action =
  | { kind: "correct"; record: MemoryRecord }
  | { kind: "forget"; record: MemoryRecord }
  | {
      kind: "review";
      suggestion: MemorySuggestion;
      decision: "approve" | "reject" | "dismiss";
      edit: boolean;
    }
  | { kind: "alias"; project: MemoryProject }
  | { kind: "workflow"; project: MemoryProject }
  | { kind: "analyze" }
  | { kind: "consolidate" }
  | {
      kind: "unlink";
      project: MemoryProject;
      linkKind: "alias" | "workflow";
      value: string;
    };

const MEMORY_VIEWS = [
  ["stored", "Stored memories"],
  ["review", "Review queue"],
  ["projects", "Project context"],
] as const;

export function MemoryPage({
  token,
  prepare,
  navigate,
}: {
  token: string;
  prepare: (message: string) => void;
  navigate?: (screen: Screen) => void;
}) {
  const [tab, setTab] = useState<"stored" | "review" | "projects">("stored");
  const [search, setSearch] = useState(""),
    [query, setQuery] = useState("");
  const [type, setType] = useState(""),
    [project, setProject] = useState(""),
    [sort, setSort] = useState("updated");
  const [offset, setOffset] = useState(0),
    [reviewOffset, setReviewOffset] = useState(0);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [selected, setSelected] = useState(""),
    [selectedSuggestion, setSelectedSuggestion] = useState("");
  const [projectId, setProjectId] = useState("");
  const [action, setAction] = useState<Action | null>(null),
    [content, setContent] = useState("");
  const [editProject, setEditProject] = useState(""),
    [semantic, setSemantic] = useState("statement");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const ledger = useRef(new MemoryRequestLedger());
  const tabsRef = useRef<HTMLDivElement>(null);
  const list = usePrivateResource<MemoryExplorerData>(
    `/api/memory/explorer?q=${encodeURIComponent(query)}&type=${encodeURIComponent(type)}&project=${encodeURIComponent(project)}&sort=${sort}&offset=${offset}&limit=30`,
    token,
  );
  const detail = usePrivateResource<MemoryDetailData>(
    `/api/memory/record/${encodeURIComponent(selected)}?offset=${historyOffset}&limit=50`,
    selected ? token : "",
    5000,
  );
  const review = usePrivateResource<MemorySuggestionsData>(
    `/api/memory/suggestions?offset=${reviewOffset}&limit=20`,
    tab === "review" ? token : "",
    5000,
  );
  const context = usePrivateResource<ProjectContextData>(
    `/api/memory/project/${encodeURIComponent(projectId)}`,
    tab === "projects" && projectId ? token : "",
    5000,
  );
  const record = currentMemory(detail.data, selected);
  const suggestion = review.data?.items.find(
    (row) => row.id === selectedSuggestion,
  );
  const projects = list.data?.projects || [];
  const offline = !token || Boolean(list.error),
    connected = !offline && list.data?.available === true;
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setOffset(0);
    }, 220);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    setSelected("");
    setSelectedSuggestion("");
    setAction(null);
    setNotice("");
    ledger.current.clear();
  }, [token]);
  useEffect(() => {
    if (
      list.data?.records.length &&
      !list.data.records.some((row) => row.id === selected)
    )
      setSelected(list.data.records[0].id);
  }, [list.data]);
  useEffect(() => {
    setHistoryOffset(0);
  }, [selected]);
  useEffect(() => {
    if (
      review.data?.items.length &&
      !review.data.items.some((row) => row.id === selectedSuggestion)
    )
      setSelectedSuggestion(review.data.items[0].id);
  }, [review.data]);
  useEffect(() => {
    if (projects.length && !projects.some((row) => row.id === projectId))
      setProjectId(projects[0].id);
  }, [list.data]);
  function refresh() {
    list.refresh();
    detail.refresh();
    review.refresh();
    context.refresh();
  }
  function open(next: Action) {
    setAction(next);
    setError("");
    ledger.current.clear();
    setContent(
      next.kind === "correct"
        ? next.record.content
        : next.kind === "review"
          ? next.suggestion.content
          : "",
    );
    if (next.kind === "correct") {
      setEditProject(
        projects.some((row) => row.id === next.record.project_id)
          ? next.record.project_id
          : "",
      );
      setSemantic(
        next.record.semantic_status === "verified_outcome"
          ? "statement"
          : next.record.semantic_status,
      );
    }
    if (next.kind === "analyze" || next.kind === "consolidate")
      setEditProject(project);
  }
  function inspectWorkflow(id: string) {
    if (navigate) {
      storeInspection("workflows", id);
      navigate("workflows");
    }
  }
  async function apply() {
    if (!action || busy || !token || !connected) return;
    setBusy(true);
    setError("");
    let operation: string, data: object;
    if (action.kind === "correct") {
      operation = "correct";
      data = correctionData(action.record, content, editProject, semantic);
    } else if (action.kind === "forget") {
      operation = "forget";
      data = {
        memory_id: action.record.id,
        expected_updated_at: action.record.updated_at,
      };
    } else if (action.kind === "review") {
      operation = "review";
      data = reviewData(
        action.suggestion,
        action.decision,
        action.edit ? content : null,
      );
    } else if (action.kind === "alias") {
      operation = "project.alias";
      data = {
        project_id: action.project.id,
        expected_fingerprint: action.project.fingerprint,
        alias: content,
      };
    } else if (action.kind === "unlink") {
      operation = "project.unlink";
      data = {
        project_id: action.project.id,
        expected_fingerprint: action.project.fingerprint,
        kind: action.linkKind,
        value: action.value,
      };
    } else if (action.kind === "analyze") {
      operation = "analyze";
      data = { content, project_id: editProject };
    } else if (action.kind === "consolidate") {
      operation = "consolidate";
      data = { project_id: editProject };
    } else {
      operation = "project.workflow";
      data = {
        project_id: action.project.id,
        expected_fingerprint: action.project.fingerprint,
        workflow_id: content,
      };
    }
    try {
      const response = await write<{ message?: string; created?: number }>(
        "/api/memory",
        token,
        ledger.current.payload(operation, data),
      );
      setNotice(
        action.kind === "forget"
          ? "Memory deleted. Related suggestions and retrieval context were invalidated."
          : action.kind === "review"
            ? `Suggestion ${action.decision === "approve" ? "approved" : action.decision === "reject" ? "rejected" : "dismissed"}.`
            : action.kind === "analyze" || action.kind === "consolidate"
              ? `${response.created ?? 0} suggestions created. ${response.message || "No authoritative memory was changed."}`
              : "Your change was saved locally.",
      );
      if (action.kind === "forget") {
        setSelected("");
        detail.setData(null);
        list.setData(null);
      }
      if (action.kind === "review") {
        setSelectedSuggestion("");
        review.setData(null);
      }
      ledger.current.clear();
      setAction(null);
      refresh();
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "The change could not be applied. Your draft is preserved.",
      );
      refresh();
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="memory-explorer">
      <header className="screen-heading">
        <div>
          <h1>Memory</h1>
          <p>What HANNI remembers, and where it came from.</p>
        </div>
        <div className="memory-header-actions">
          <button
            disabled={!connected}
            onClick={() => prepare("Remember that ")}
          >
            Add through HANNI
          </button>
          <button className="text-link" onClick={refresh}>
            Refresh
          </button>
        </div>
      </header>
      <div className="memory-status-line">
        <span>
          {connected
            ? "Local memory"
            : offline
              ? "Connection unavailable"
              : "Memory unavailable"}
        </span>
        <span>
          {connected
            ? `${list.data!.total_stored} stored`
            : "Stored count unavailable"}
        </span>
        <span>LAYA: {words(list.data?.status.mode || "unavailable")}</span>
        <details className="memory-mode-details">
          <summary>Mode details</summary>
          <p>
            {list.data?.status.description ||
              "Connect to inspect the active inference mode."}{" "}
            This page uses local keyword search; semantic search is{" "}
            {list.data?.status.semantic_search_available
              ? "enabled"
              : "not enabled"}
            .
          </p>
        </details>
      </div>
      <div
        ref={tabsRef}
        className="memory-tabs"
        role="tablist"
        aria-label="Memory views"
      >
        {MEMORY_VIEWS.map(([id, label], index) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => setTab(id)}
            onKeyDown={(event) => {
              const target =
                event.key === "ArrowRight"
                  ? (index + 1) % MEMORY_VIEWS.length
                  : event.key === "ArrowLeft"
                    ? (index + MEMORY_VIEWS.length - 1) % MEMORY_VIEWS.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? MEMORY_VIEWS.length - 1
                        : null;
              if (target === null) return;
              event.preventDefault();
              setTab(MEMORY_VIEWS[target][0]);
              tabsRef.current
                ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
                [target]?.focus();
            }}
          >
            {label}
            {id === "review" &&
              connected &&
              list.data!.pending_suggestions > 0 && (
                <span>{list.data!.pending_suggestions}</span>
              )}
          </button>
        ))}
      </div>
      {notice && (
        <p className="memory-notice" role="status">
          {notice}
        </p>
      )}
      {offline && (
        <Empty title="Local memory is offline">
          {list.error ||
            "Connect to the local HANNI session to inspect private records."}{" "}
          Saved records remain on this computer. Changes are disabled until the
          service reconnects.
        </Empty>
      )}
      {!offline && !list.data && <Loading />}
      {!offline && list.data && !list.data.available && (
        <Empty title="Memory is unavailable">
          {list.data.reason || "Durable memory is disabled in this session."}
        </Empty>
      )}
      {connected && tab === "stored" && (
        <>
          <div className="memory-search">
            <label>
              Search
              <input
                type="search"
                value={search}
                maxLength={500}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Keywords, decisions, project names"
              />
            </label>
            <label>
              Project
              <select
                value={project}
                onChange={(e) => {
                  setProject(e.target.value);
                  setOffset(0);
                  setSelected("");
                }}
              >
                <option value="">All projects</option>
                {projects.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Type
              <select
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All types</option>
                {[
                  "fact",
                  "preference",
                  "project",
                  "decision",
                  "correction",
                  "workflow",
                  "device",
                ].map((kind) => (
                  <option key={kind} value={kind}>
                    {words(kind)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Order
              <select
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="updated">Recently updated</option>
                <option value="created">Recently created</option>
              </select>
            </label>
          </div>
          <p className="memory-search-note">
            Local keyword search · approved stored records
          </p>
          <div className="memory-browser">
            <section
              className="memory-index"
              aria-label="Stored memory records"
            >
              <div className="memory-list-label">
                <span>
                  {list.data!.records.length
                    ? `${offset + 1}–${offset + list.data!.records.length}`
                    : "0 records"}
                </span>
                <span>
                  {list.data!.filtered_count == null
                    ? "Matching keywords"
                    : `${list.data!.filtered_count} in view`}
                </span>
              </div>
              {list.data!.records.length ? (
                list.data!.records.map((row) => (
                  <button
                    className={`memory-index-row ${selected === row.id ? "selected" : ""}`}
                    key={row.id}
                    onClick={() => setSelected(row.id)}
                    aria-pressed={selected === row.id}
                  >
                    <span className="memory-row-kind">
                      {words(row.memory_type)}
                      <time>{date(row.updated_at)}</time>
                    </span>
                    <strong>{row.content}</strong>
                    <span className="memory-row-source">
                      {words(row.semantic_status)} ·{" "}
                      {projects.find((p) => p.id === row.project_id)?.name ||
                        "No project"}
                    </span>
                  </button>
                ))
              ) : (
                <Empty
                  title={
                    query || project || type
                      ? "No matching memories"
                      : "No saved memories yet"
                  }
                >
                  {query || project || type
                    ? "Try fewer keywords or clear the project and type filters."
                    : "Use an explicit remember request to save a fact or preference. Suggestions stay separate until you review them."}
                </Empty>
              )}
              <div className="memory-pagination">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 30))}
                >
                  Previous
                </button>
                <button
                  disabled={!list.data!.has_more}
                  onClick={() => setOffset(offset + 30)}
                >
                  Next
                </button>
              </div>
            </section>
            <section
              className="memory-detail"
              aria-label="Selected memory details"
            >
              {!selected ? (
                <Empty title="Select a memory">
                  Inspect its content, source and changes before editing.
                </Empty>
              ) : detail.error ? (
                <Empty title="Record unavailable">
                  {detail.error} Refresh before changing this memory.
                </Empty>
              ) : !record ? (
                detail.data?.record === null ? (
                  <Empty title="This memory is no longer available">
                    {detail.data.reason ||
                      "It may have been deleted in another session."}
                  </Empty>
                ) : (
                  <Loading />
                )
              ) : (
                <>
                  <div className="memory-detail-heading">
                    <span>{words(record.memory_type)}</span>
                    <span>{words(record.semantic_status)}</span>
                  </div>
                  <h2>Saved record</h2>
                  <p className="memory-content">{record.content}</p>
                  <div className="memory-detail-actions">
                    <button
                      disabled={!connected || Boolean(detail.error)}
                      onClick={() => open({ kind: "correct", record })}
                    >
                      Correct memory
                    </button>
                    <button
                      className="text-link memory-delete"
                      disabled={!connected || Boolean(detail.error)}
                      onClick={() => open({ kind: "forget", record })}
                    >
                      Delete
                    </button>
                  </div>
                  <section className="memory-source">
                    <h3>Source & context</h3>
                    <dl>
                      <div>
                        <dt>Source</dt>
                        <dd>{record.source || "Not recorded"}</dd>
                      </div>
                      <div>
                        <dt>Reference</dt>
                        <dd>
                          {record.source_ref ||
                            "No original reference was retained"}
                        </dd>
                      </div>
                      <div>
                        <dt>Project</dt>
                        <dd>
                          {detail.data?.project?.name ||
                            (detail.data?.project_missing
                              ? "Project no longer exists; memory remains stored"
                              : "Unassigned")}
                        </dd>
                      </div>
                      <div>
                        <dt>Created</dt>
                        <dd>{date(record.created_at)}</dd>
                      </div>
                      <div>
                        <dt>Updated</dt>
                        <dd>{date(record.updated_at)}</dd>
                      </div>
                      <div>
                        <dt>Record ID</dt>
                        <dd className="memory-mono">{record.id}</dd>
                      </div>
                    </dl>
                    <p className="memory-help">
                      This record preserves its source. Extraction confidence is
                      uncalibrated and is not shown as a probability. An owner
                      statement does not prove that a workflow completed.
                    </p>
                  </section>
                  <section className="memory-history">
                    <h3>Correction history</h3>
                    {detail.data?.history.length ? (
                      detail.data.history.map((row, index) => (
                        <details key={`${row.updated_at}-${index}`}>
                          <summary>
                            {date(row.updated_at)} · {row.source}
                          </summary>
                          <p>{row.content}</p>
                          <small>
                            {words(row.semantic_status || "statement")}
                          </small>
                        </details>
                      ))
                    ) : (
                      <p className="memory-help">
                        {detail.data?.history_withheld
                          ? "Earlier correction content is withheld by the memory privacy policy."
                          : "No earlier correction was retained."}{" "}
                        History is removed when you delete this memory.
                      </p>
                    )}
                    {(detail.data?.history_count || 0) > 50 && (
                      <div className="memory-pagination">
                        <button
                          disabled={historyOffset === 0}
                          onClick={() =>
                            setHistoryOffset(Math.max(0, historyOffset - 50))
                          }
                        >
                          Newer corrections
                        </button>
                        <button
                          disabled={!detail.data?.history_has_more}
                          onClick={() => setHistoryOffset(historyOffset + 50)}
                        >
                          Older corrections
                        </button>
                      </div>
                    )}
                  </section>
                </>
              )}
            </section>
          </div>
        </>
      )}
      {connected && tab === "review" && (
        <>
          <div className="memory-review-toolbar">
            <span>
              Local rule suggestions · model inference is{" "}
              {list.data!.status.model_inference_active
                ? "active in the displayed mode"
                : "not active"}
            </span>
            <button onClick={() => open({ kind: "analyze" })}>
              Suggest from a statement
            </button>
            <button onClick={() => open({ kind: "consolidate" })}>
              Find related records
            </button>
          </div>
          <p className="memory-section-intro">
            Proposals are untrusted suggestions. Review the source, uncertainty
            and exact change before approving. Nothing is saved as a fact merely
            because LAYA suggested it.
          </p>
          {review.error ? (
            <Empty title="Review queue unavailable">{review.error}</Empty>
          ) : !review.data ? (
            <Loading />
          ) : (
            <div className="memory-browser">
              <section
                className="memory-index"
                aria-label="Pending memory suggestions"
              >
                <div className="memory-list-label">
                  <span>Pending review</span>
                  <span>{review.data.total} suggestions</span>
                </div>
                {review.data.items.length ? (
                  review.data.items.map((row) => (
                    <button
                      key={row.id}
                      className={`memory-index-row ${selectedSuggestion === row.id ? "selected" : ""}`}
                      onClick={() => setSelectedSuggestion(row.id)}
                    >
                      <span className="memory-row-kind">
                        {words(row.kind)}
                        <time>{date(row.created_at)}</time>
                      </span>
                      <strong>{row.content}</strong>
                      <span className="memory-row-source">{row.source}</span>
                    </button>
                  ))
                ) : (
                  <Empty title="Nothing awaiting review">
                    LAYA has no persisted pending proposals. Local memories
                    remain available while inference is disabled or unavailable.
                  </Empty>
                )}
                <div className="memory-pagination">
                  <button
                    disabled={reviewOffset === 0}
                    onClick={() =>
                      setReviewOffset(Math.max(0, reviewOffset - 20))
                    }
                  >
                    Previous
                  </button>
                  <button
                    disabled={!review.data.has_more}
                    onClick={() => setReviewOffset(reviewOffset + 20)}
                  >
                    Next
                  </button>
                </div>
              </section>
              <section
                className="memory-detail"
                aria-label="Suggestion details"
              >
                {suggestion ? (
                  <>
                    <div className="memory-detail-heading">
                      <span>{words(suggestion.kind)}</span>
                      <span>Pending · {words(suggestion.semantic_status)}</span>
                    </div>
                    <h2>Proposed memory</h2>
                    <p className="memory-content">{suggestion.content}</p>
                    <section className="memory-source">
                      <h3>Why this was proposed</h3>
                      <p>
                        {suggestion.reason ||
                          "No rationale was retained. Inspect the source before approval."}
                      </p>
                      <dl>
                        <div>
                          <dt>Source</dt>
                          <dd>{suggestion.source}</dd>
                        </div>
                        <div>
                          <dt>Reference</dt>
                          <dd>
                            {suggestion.source_ref ||
                              "No original source reference"}
                          </dd>
                        </div>
                        <div>
                          <dt>Uncertainty</dt>
                          <dd>
                            {suggestion.uncertainty ||
                              "Not independently verified"}
                          </dd>
                        </div>
                        <div>
                          <dt>Related records</dt>
                          <dd>
                            {suggestion.related_ids.length
                              ? suggestion.related_ids.join(", ")
                              : "None linked"}
                          </dd>
                        </div>
                        <div>
                          <dt>Approval change</dt>
                          <dd>
                            {suggestion.kind === "add"
                              ? "Add this exact text through HANNI's privacy-checked owner memory pathway."
                              : suggestion.kind === "correct"
                                ? `Correct record ${suggestion.target_id} only if its inspected version is unchanged.`
                                : "This consolidation needs explicit record correction or deletion. It cannot automatically erase or resolve conflicting memories."}
                          </dd>
                        </div>
                      </dl>
                    </section>
                    <div className="memory-review-actions">
                      <button
                        disabled={
                          !connected || !suggestionApplyAllowed(suggestion)
                        }
                        onClick={() =>
                          open({
                            kind: "review",
                            suggestion,
                            decision: "approve",
                            edit: false,
                          })
                        }
                      >
                        Approve
                      </button>
                      <button
                        disabled={
                          !connected || !suggestionApplyAllowed(suggestion)
                        }
                        onClick={() =>
                          open({
                            kind: "review",
                            suggestion,
                            decision: "approve",
                            edit: true,
                          })
                        }
                      >
                        Edit & approve
                      </button>
                      <button
                        disabled={!connected}
                        onClick={() =>
                          open({
                            kind: "review",
                            suggestion,
                            decision: "reject",
                            edit: false,
                          })
                        }
                      >
                        Reject
                      </button>
                      <button
                        className="text-link"
                        disabled={!connected}
                        onClick={() =>
                          open({
                            kind: "review",
                            suggestion,
                            decision: "dismiss",
                            edit: false,
                          })
                        }
                      >
                        Dismiss
                      </button>
                    </div>
                    {suggestion.target_id && (
                      <button
                        className="text-link"
                        onClick={() => {
                          setSelected(suggestion.target_id);
                          setTab("stored");
                        }}
                      >
                        Inspect target record
                      </button>
                    )}
                  </>
                ) : (
                  <Empty title="Select a suggestion">
                    See what would change and inspect the supporting source.
                  </Empty>
                )}
              </section>
            </div>
          )}
        </>
      )}
      {connected && tab === "projects" && (
        <div className="memory-projects">
          <aside className="memory-project-index" aria-label="Saved projects">
            {projects.length ? (
              projects.map((row) => (
                <button
                  key={row.id}
                  className={projectId === row.id ? "selected" : ""}
                  onClick={() => setProjectId(row.id)}
                >
                  <strong>{row.name}</strong>
                  <small>
                    {row.aliases.length
                      ? row.aliases.join(" · ")
                      : "No saved aliases"}
                  </small>
                </button>
              ))
            ) : (
              <Empty title="No projects yet">
                Create a project in Workspace → Projects. Assign memories to its
                stable identity here.
              </Empty>
            )}
          </aside>
          <section
            className="memory-project-detail"
            aria-label="Project memory context"
          >
            {!projectId ? (
              <Empty title="Project continuity starts with a saved project">
                Project notes, approved memories and explicitly linked workflows
                remain distinct sources.
              </Empty>
            ) : context.error ? (
              <Empty title="Project context unavailable">{context.error}</Empty>
            ) : context.data?.context.project.id !== projectId ? (
              <Loading />
            ) : (
              <ProjectView
                data={context.data}
                open={open}
                inspectWorkflow={inspectWorkflow}
                connected={connected}
              />
            )}
          </section>
        </div>
      )}
      {action && (
        <FeatureDialog
          title={
            action.kind === "correct"
              ? "Correct this memory"
              : action.kind === "forget"
                ? "Delete this memory?"
                : action.kind === "review"
                  ? `${action.decision === "approve" ? "Approve" : action.decision === "reject" ? "Reject" : "Dismiss"} this suggestion?`
                  : action.kind === "alias"
                    ? "Add a project alias"
                    : action.kind === "unlink"
                      ? "Remove this project link?"
                      : action.kind === "analyze"
                        ? "Suggest a memory from a statement"
                        : action.kind === "consolidate"
                          ? "Review memory relationships"
                          : "Link a workflow"
          }
          onClose={() => setAction(null)}
          busy={busy}
        >
          {action.kind === "analyze" || action.kind === "consolidate" ? (
            <>
              <p className="memory-dialog-copy">
                {action.kind === "analyze"
                  ? "Provide an explicit statement to evaluate with conservative local rules. Plans remain plans. Questions, uncertain inferences and sensitive text are excluded. Any candidate still needs your review before becoming a memory."
                  : "Inspect up to 200 authorized records with local rules. Exact duplicates, explicit shared projects, conflicting fact keys and older records can produce review suggestions. Recency does not select a winner, and no memory is corrected or deleted."}
              </p>
              {action.kind === "analyze" && (
                <label className="memory-dialog-label">
                  Owner statement
                  <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    maxLength={1200}
                    rows={5}
                    placeholder="An explicit reusable fact, preference, decision or project plan"
                  />
                </label>
              )}
              <label className="memory-dialog-label">
                Project scope
                <select
                  value={editProject}
                  onChange={(e) => setEditProject(e.target.value)}
                >
                  <option value="">
                    {action.kind === "consolidate"
                      ? "All projects"
                      : "Unassigned"}
                  </option>
                  {projects.map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <p className="memory-help">
                This creates local review proposals. It does not invoke LAYA or
                transmit stored memories.
              </p>
            </>
          ) : action.kind === "unlink" ? (
            <>
              <p className="memory-dialog-copy">
                Remove this explicit {action.linkKind} association from{" "}
                {action.project.name}. The underlying project, memories and
                workflow remain stored.
              </p>
              <p className="memory-confirm-content">{action.value}</p>
            </>
          ) : action.kind === "forget" ? (
            <>
              <p className="memory-dialog-copy">
                Delete this exact record and its retained correction history.
                Dependent suggestions and context are invalidated. Conversation
                history and project notes are separate.
              </p>
              <p className="memory-confirm-content">{action.record.content}</p>
            </>
          ) : action.kind === "correct" ? (
            <>
              <label className="memory-dialog-label">
                Corrected content
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  maxLength={1200}
                  rows={5}
                />
              </label>
              <div className="memory-dialog-fields">
                <label>
                  Project
                  <select
                    value={editProject}
                    onChange={(e) => setEditProject(e.target.value)}
                  >
                    <option value="">Unassigned</option>
                    {projects.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Statement type
                  <select
                    value={semantic}
                    onChange={(e) => setSemantic(e.target.value)}
                  >
                    {[
                      "statement",
                      "plan",
                      "decision",
                      "question",
                      "hypothetical",
                      "inference",
                      "completed_claim",
                      "historical",
                      "failed_claim",
                      "temporary",
                    ].map((kind) => (
                      <option key={kind} value={kind}>
                        {words(kind)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="memory-help">
                This preserves the record ID and retains the prior content as
                correction history. Current version:{" "}
                {date(action.record.updated_at)}. This action cannot certify
                workflow completion.
              </p>
            </>
          ) : action.kind === "review" ? (
            <>
              <p className="memory-dialog-copy">
                {action.decision === "approve"
                  ? "Apply the displayed text through HANNI's owner-controlled memory pathway. Stale suggestions and changed targets are rejected."
                  : action.decision === "reject"
                    ? "Record that this proposal is incorrect or should not become a saved memory."
                    : "Remove this proposal from the pending queue without saving its content as a memory."}
              </p>
              {action.edit ? (
                <label className="memory-dialog-label">
                  Memory to approve
                  <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    maxLength={1200}
                    rows={5}
                  />
                </label>
              ) : (
                <p className="memory-confirm-content">
                  {action.suggestion.content}
                </p>
              )}
            </>
          ) : (
            <>
              <p className="memory-dialog-copy">
                {action.kind === "alias"
                  ? "Give this existing project a distinctive name HANNI can recognize. Shared aliases remain ambiguous."
                  : "Enter an existing workflow ID. This only links its history; it does not start or resume execution."}
              </p>
              <label className="memory-dialog-label">
                {action.kind === "alias" ? "Alias" : "Workflow ID"}
                <input
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  maxLength={action.kind === "alias" ? 200 : 103}
                  placeholder={
                    action.kind === "alias"
                      ? "A distinctive project name"
                      : "wf_…"
                  }
                />
              </label>
            </>
          )}
          {error && (
            <p className="feature-error" role="alert">
              {error} Refresh and inspect the current record if it changed. Your
              draft remains here.
            </p>
          )}
          <div className="dialog-actions">
            <button autoFocus disabled={busy} onClick={() => setAction(null)}>
              Cancel
            </button>
            <button
              className={action.kind === "forget" ? "danger-button" : ""}
              disabled={
                busy ||
                !connected ||
                ((action.kind === "correct" ||
                  action.kind === "analyze" ||
                  action.kind === "alias" ||
                  action.kind === "workflow" ||
                  (action.kind === "review" && action.edit)) &&
                  !content.trim())
              }
              onClick={apply}
            >
              {busy
                ? "Saving…"
                : action.kind === "forget"
                  ? "Delete memory"
                  : action.kind === "review"
                    ? action.decision === "approve"
                      ? "Approve memory"
                      : action.decision === "reject"
                        ? "Reject suggestion"
                        : "Dismiss suggestion"
                    : action.kind === "analyze"
                      ? "Create suggestion"
                      : action.kind === "consolidate"
                        ? "Find suggestions"
                        : "Save change"}
            </button>
          </div>
        </FeatureDialog>
      )}
    </div>
  );
}

function ProjectView({
  data,
  open,
  inspectWorkflow,
  connected,
}: {
  data: ProjectContextData;
  open: (action: Action) => void;
  inspectWorkflow: (id: string) => void;
  connected: boolean;
}) {
  const ctx = data.context;
  return (
    <>
      <div className="memory-project-heading">
        <div>
          <span className="field-label">Project context</span>
          <h2>{ctx.project.name}</h2>
          <p>
            {ctx.project.description || "No project description was saved."}
          </p>
        </div>
        <button
          className="text-link"
          disabled={!connected}
          onClick={() => open({ kind: "alias", project: ctx.project })}
        >
          Add alias
        </button>
      </div>
      <section className="memory-project-section">
        <h3>Verified progress</h3>
        {ctx.verified_results.length ? (
          ctx.verified_results.map((row) => (
            <article key={`${row.workflow_id}-${row.step_id}`}>
              <p>{row.summary}</p>
              <small>{date(row.finished_at)} · verified workflow receipt</small>
              <button
                className="text-link"
                onClick={() => inspectWorkflow(row.workflow_id)}
              >
                Inspect {row.workflow_id}
              </button>
            </article>
          ))
        ) : (
          <p className="memory-help">
            No verified workflow result is linked. Discussed plans and saved
            statements do not establish completed work.
          </p>
        )}
      </section>
      <section className="memory-project-section">
        <h3>Decisions & plans</h3>
        {ctx.decisions.length || ctx.plans.length ? (
          [...ctx.decisions, ...ctx.plans].map((row) => (
            <article key={row.id}>
              <span className="field-label">{words(row.semantic_status)}</span>
              <p>{row.content}</p>
              <small>
                Memory {row.id} · {row.source}
              </small>
            </article>
          ))
        ) : (
          <p className="memory-help">
            No approved decisions or plans are assigned to this project.
          </p>
        )}
      </section>
      <section className="memory-project-section">
        <h3>Known issues</h3>
        {ctx.known_issues.length ? (
          ctx.known_issues.map((row, index) => (
            <article key={index}>
              <p>{row.summary}</p>
              <small>
                {row.status} · {row.workflow_id}/{row.step_id}
              </small>
            </article>
          ))
        ) : (
          <p className="memory-help">
            No failed or unverified step is present in the linked workflow
            history.
          </p>
        )}
      </section>
      <section className="memory-project-section">
        <div className="memory-section-heading">
          <h3>Workflow history</h3>
          <button
            className="text-link"
            disabled={!connected}
            onClick={() => open({ kind: "workflow", project: ctx.project })}
          >
            Link workflow
          </button>
        </div>
        {ctx.workflow_history.length ? (
          ctx.workflow_history.map((row) => (
            <button
              key={row.workflow_id}
              className="memory-workflow-row"
              onClick={() => inspectWorkflow(row.workflow_id)}
            >
              <strong>{row.goal || row.workflow_id}</strong>
              <span>{words(row.status)}</span>
              <small>
                {date(row.updated_at)} · revision {row.revision}
              </small>
            </button>
          ))
        ) : (
          <p className="memory-help">
            Link an existing workflow explicitly to include its checkpoints and
            outcomes. A shared project name alone does not create a
            relationship.
          </p>
        )}
      </section>
      {(ctx.project.aliases.length > 0 || ctx.workflow_links.length > 0) && (
        <section className="memory-project-section">
          <h3>Explicit associations</h3>
          {ctx.project.aliases.map((value) => (
            <div className="memory-association" key={value}>
              <span>Alias: {value}</span>
              <button
                className="text-link"
                onClick={() =>
                  open({
                    kind: "unlink",
                    project: ctx.project,
                    linkKind: "alias",
                    value,
                  })
                }
              >
                Remove
              </button>
            </div>
          ))}
          {ctx.workflow_links.map((row) => (
            <div className="memory-association" key={row.workflow_id}>
              <span>Workflow: {row.workflow_id}</span>
              <button
                className="text-link"
                onClick={() =>
                  open({
                    kind: "unlink",
                    project: ctx.project,
                    linkKind: "workflow",
                    value: row.workflow_id,
                  })
                }
              >
                Unlink
              </button>
            </div>
          ))}
        </section>
      )}
      <section className="memory-project-section">
        <h3>Related files & notes</h3>
        {ctx.files.length || ctx.notes.length ? (
          <>
            {ctx.files.map((row) => (
              <article key={row.id}>
                <strong>{row.label}</strong>
                <p className="memory-mono">{row.target}</p>
                <small>Owner-linked {row.kind}; contents were not read.</small>
              </article>
            ))}
            {ctx.notes.map((row) => (
              <details key={row.id}>
                <summary>{row.title} · owner project note</summary>
                <p>{row.body}</p>
              </details>
            ))}
          </>
        ) : (
          <p className="memory-help">
            No file, conversation or project note is linked.
          </p>
        )}
      </section>
      <section className="memory-project-section">
        <h3>Approved project memories</h3>
        {ctx.memories.length ? (
          ctx.memories.map((row) => (
            <article key={row.id}>
              <p>{row.content}</p>
              <small>
                {words(row.semantic_status)} · memory {row.id} · {row.source}
              </small>
            </article>
          ))
        ) : (
          <p className="memory-help">
            Assign a memory to this project using Correct memory.
          </p>
        )}
      </section>
      {ctx.uncertainties.length > 0 && (
        <section className="memory-project-section memory-uncertainty">
          <h3>What is not established</h3>
          {ctx.uncertainties.map((row) => (
            <p key={row}>{row}</p>
          ))}
        </section>
      )}
      <details className="memory-context-source">
        <summary>
          Inspect compact context package · {ctx.context_chars} characters
        </summary>
        <pre>{ctx.context_text}</pre>
        {ctx.omitted_context_lines > 0 && (
          <p>
            {ctx.omitted_context_lines} lines omitted to respect the context
            budget.
          </p>
        )}
      </details>
    </>
  );
}
