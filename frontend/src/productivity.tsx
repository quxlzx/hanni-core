import { useEffect, useRef, useState, type FormEvent } from "react";
import { write } from "./api";
import { FeatureDialog } from "./feature_ui";
import { taskDuePayload } from "./task_due";
import {
  usePrivateResource,
  consumeInspection,
  storeInspection,
  type WorkspaceData,
  type TaskRecord,
  type ProjectRecord,
  type NoteRecord,
  type LinkRecord,
  type CalendarData,
} from "./feature_types";
import type { Screen } from "./types";
import "./productivity.css";

type View = "planner" | "tasks" | "calendar" | "projects";
type Editor = {
  kind: "task" | "project" | "note" | "link";
  id?: string;
  fingerprint?: string;
  originalDue?: string;
};
const localDate = (date: Date) => {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};
const today = () => localDate(new Date());
const dueLabel = (task: TaskRecord) =>
  task.due
    ? new Date(task.due).toLocaleDateString([], {
        month: "short",
        day: "numeric",
      })
    : "No due date";

export function WorkspacePage({
  view,
  token,
  prepare,
  navigate,
}: {
  view: View;
  token: string;
  prepare: (message: string) => void;
  navigate: (screen: Screen | "calendar") => void;
}) {
  const resource = usePrivateResource<WorkspaceData>(
    "/api/productivity",
    token,
  );
  const [day, setDay] = useState(today),
    [days, setDays] = useState(7),
    [calendarRevision, setCalendarRevision] = useState(0);
  const calendar = usePrivateResource<CalendarData>(
    `/api/calendar?start_date=${day}&days=${days}${calendarRevision ? `&refresh=1&revision=${calendarRevision}` : ""}`,
    token,
    0,
  );
  const [search, setSearch] = useState(""),
    [status, setStatus] = useState("open"),
    [project, setProject] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [confirmation, setConfirmation] = useState<{
    operation: string;
    data: unknown;
    title: string;
    description: string;
  } | null>(null);
  const [form, setForm] = useState({
    title: "",
    body: "",
    course: "",
    due: "",
    priority: "normal",
    project_id: "",
    status: "open",
    target: "",
    kind: "file",
  });
  const pending = useRef<{ signature: string; id: string } | null>(null);
  const data = resource.data;
  const writeBlocked =
    busy || !token || Boolean(resource.error) || !data?.available;
  const calendarStale = Boolean(
    calendar.data &&
    (calendar.data.stale ||
      calendar.error ||
      calendar.data.start_date !== day ||
      calendar.data.days !== days),
  );
  const rangeEnd = new Date(`${day}T12:00:00`);
  rangeEnd.setDate(rangeEnd.getDate() + days);
  const rangeEndDay = localDate(rangeEnd);
  const calendarDeadlines = (data?.tasks || [])
    .filter((task) => {
      if (!task.due || task.status !== "open") return false;
      const dueDay = localDate(new Date(task.due));
      return dueDay >= day && dueDay < rangeEndDay;
    })
    .sort((a, b) => a.due.localeCompare(b.due));
  const [inspectedTask, setInspectedTask] = useState("");
  useEffect(() => {
    if (!data || view !== "tasks") return;
    const target = consumeInspection("tasks");
    if (!target) return;
    setStatus("all");
    setSearch("");
    setProject("");
    if (!data.tasks.some((task) => task.id === target)) {
      setNotice("The related task is no longer available in this workspace.");
      return;
    }
    setInspectedTask(target);
    requestAnimationFrame(() => {
      for (const element of document.querySelectorAll<HTMLElement>(
        "[data-task]",
      )) {
        if (element.dataset.task === target) {
          element.scrollIntoView({ block: "center" });
          element.querySelector<HTMLButtonElement>(".task-title")?.focus();
          break;
        }
      }
    });
  }, [data, view]);
  const selectedProject = data?.projects.find(
    (record) => record.id === project,
  );
  function openEditor(
    kind: Editor["kind"],
    item?: TaskRecord | ProjectRecord | NoteRecord | LinkRecord,
  ) {
    setError("");
    pending.current = null;
    setEditor({
      kind,
      id: item?.id,
      fingerprint: item && "fingerprint" in item ? item.fingerprint : undefined,
      originalDue:
        item && "due" in item ? taskDuePayload(item) || undefined : undefined,
    });
    setForm({
      title: item
        ? "title" in item
          ? item.title
          : "name" in item
            ? item.name
            : item.label
        : "",
      body:
        item && "body" in item
          ? item.body
          : item && "description" in item
            ? item.description
            : "",
      course: item && "course" in item ? item.course : "",
      due: item && "due" in item ? item.due.slice(0, 10) : "",
      priority: item && "priority" in item ? item.priority : "normal",
      project_id:
        item && "project_id" in item ? item.project_id || "" : project,
      status: item && "status" in item ? item.status : "open",
      target: item && "target" in item ? item.target : "",
      kind: item && "kind" in item ? item.kind : "file",
    });
  }
  async function execute(operation: string, payload: unknown) {
    if (writeBlocked) {
      setError(
        "Reconnect and refresh the workspace before saving. Your draft is retained.",
      );
      return false;
    }
    const signature = JSON.stringify([operation, payload]);
    if (!pending.current || pending.current.signature !== signature)
      pending.current = { signature, id: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await write<{ backup_file?: string }>(
        "/api/productivity",
        token,
        { id: pending.current.id, operation, data: payload, confirmed: true },
      );
      pending.current = null;
      resource.refresh();
      setNotice(
        result.backup_file
          ? `Backup saved: ${result.backup_file}`
          : "Workspace saved.",
      );
      return true;
    } catch (error) {
      setError(
        `${error instanceof Error ? error.message : "Could not save."} Check saved records before retrying. Your draft is retained.`,
      );
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!editor) return;
    let operation = `${editor.kind}.${editor.id ? "update" : "create"}`,
      payload: Record<string, unknown> = {};
    if (editor.kind === "task")
      payload = {
        title: form.title,
        course: form.course,
        due:
          editor.originalDue && form.due === editor.originalDue.slice(0, 10)
            ? editor.originalDue
            : form.due || null,
        priority: form.priority,
        project_id: form.project_id || null,
        ...(editor.id
          ? {
              task_id: editor.id,
              expected_fingerprint: editor.fingerprint,
              status: form.status,
            }
          : {}),
      };
    if (editor.kind === "project")
      payload = {
        name: form.title,
        description: form.body,
        ...(editor.id
          ? { project_id: editor.id, expected_fingerprint: editor.fingerprint }
          : {}),
      };
    if (editor.kind === "note")
      payload = {
        title: form.title,
        body: form.body,
        ...(editor.id
          ? { note_id: editor.id, expected_fingerprint: editor.fingerprint }
          : { project_id: form.project_id }),
      };
    if (editor.kind === "link") {
      operation = "link.create";
      payload = {
        project_id: form.project_id,
        label: form.title,
        target: form.target,
        kind: form.kind,
      };
    }
    if (await execute(operation, payload)) setEditor(null);
  }
  const tasks = (data?.tasks || [])
    .filter(
      (task) =>
        (view === "planner"
          ? task.status === "open" &&
            (!task.due || task.due.slice(0, 10) <= today())
          : view === "projects" ||
            status === "all" ||
            task.status === status) &&
        (!search ||
          `${task.title} ${task.course}`
            .toLowerCase()
            .includes(search.toLowerCase())) &&
        (!project || task.project_id === project),
    )
    .sort(
      (a, b) =>
        ({ high: 0, normal: 1, low: 2 })[a.priority] -
          { high: 0, normal: 1, low: 2 }[b.priority] ||
        a.due.localeCompare(b.due),
    );
  const taskList = (
    <div className="workspace-task-list">
      {tasks.length ? (
        tasks.map((task) => (
          <div
            key={task.id}
            data-task={task.id}
            className={`workspace-task ${task.status} ${inspectedTask === task.id ? "inspected" : ""}`}
          >
            <button
              className="task-check"
              aria-label={`${task.status === "completed" ? "Reopen" : "Complete"} ${task.title}`}
              aria-pressed={task.status === "completed"}
              disabled={busy || !token || Boolean(resource.error)}
              onClick={() =>
                execute("task.update", {
                  task_id: task.id,
                  expected_fingerprint: task.fingerprint,
                  title: task.title,
                  course: task.course,
                  due: taskDuePayload(task),
                  priority: task.priority,
                  project_id: task.project_id,
                  status: task.status === "open" ? "completed" : "open",
                })
              }
            >
              {task.status === "completed" ? "✓" : ""}
            </button>
            <button
              className="task-title"
              onClick={() => openEditor("task", task)}
            >
              <strong>{task.title}</strong>
              <small>
                {task.course ||
                  data?.projects.find((item) => item.id === task.project_id)
                    ?.name ||
                  "Personal"}
              </small>
            </button>
            <span className={`task-priority ${task.priority}`}>
              {task.priority}
            </span>
            <time
              className={
                task.due &&
                task.due.slice(0, 10) < today() &&
                task.status === "open"
                  ? "warning"
                  : ""
              }
            >
              {dueLabel(task)}
            </time>
            <button
              className="text-link"
              aria-label={`Delete ${task.title}`}
              onClick={() => {
                pending.current = null;
                setConfirmation({
                  operation: "task.delete",
                  data: {
                    task_id: task.id,
                    expected_fingerprint: task.fingerprint,
                  },
                  title: `Delete ${task.title}?`,
                  description:
                    "This removes the saved local task. It does not undo any executed action.",
                });
              }}
            >
              Delete
            </button>
          </div>
        ))
      ) : (
        <p className="feature-empty">
          {search || project
            ? "No tasks match your filters."
            : view === "planner"
              ? "No open tasks need attention today."
              : "No tasks in this view. Create a task to get started."}
        </p>
      )}
    </div>
  );
  const calendarList = (
    <div className="calendar-list">
      {calendar.error && (
        <p className="feature-error" role="status">
          {calendar.error}
        </p>
      )}
      {calendarStale && (
        <p className="feature-note warning">
          Last loaded schedule for {calendar.data?.start_date} (
          {calendar.data?.days} day{calendar.data?.days === 1 ? "" : "s"})
          {calendar.data?.cached_at
            ? ` from ${new Date(calendar.data.cached_at).toLocaleString()}`
            : ""}
          . Refresh for current events.
        </p>
      )}
      {!!calendar.data?.events.length && calendar.data.reason && (
        <p className="feature-note">{calendar.data.reason}</p>
      )}
      {calendar.data?.events.length ? (
        calendar.data.events.map((event, index) => (
          <div key={`${event.id}-${index}`}>
            <time>
              {event.all_day
                ? new Date(
                    `${event.start.slice(0, 10)}T12:00:00`,
                  ).toLocaleDateString()
                : new Date(event.start).toLocaleString([], {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
            </time>
            <div>
              <strong>{event.title || "Untitled event"}</strong>
              <small>
                {event.calendar || "Calendar"}
                {event.end && !event.all_day
                  ? ` · Ends ${new Date(event.end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                  : ""}
              </small>
            </div>
          </div>
        ))
      ) : (
        <section className="calendar-connection-state">
          <h2>
            {!calendar.data
              ? "Calendar status"
              : calendar.data.connected
                ? "No events loaded"
                : "Calendar connection"}
          </h2>
          <p>
            {!calendar.data
              ? calendar.error
                ? "Calendar status is unavailable. Retry when connected."
                : "Loading the saved calendar status."
              : calendar.data.reason ||
                (calendar.data.connected
                  ? "No events loaded for this range. Refresh the authorized calendar."
                  : "No connected calendar account is available.")}
          </p>
        </section>
      )}
    </div>
  );
  return (
    <div className="productivity-page">
      <header className="screen-heading">
        <div>
          <h1>{view[0].toUpperCase() + view.slice(1)}</h1>
          <p>
            {view === "planner"
              ? "Today and upcoming work"
              : view === "calendar"
                ? "Authorized calendar and cached schedules"
                : "Saved on this computer"}
          </p>
        </div>
        <div className="feature-header-actions">
          {view === "tasks" || view === "planner" ? (
            <button
              disabled={!token || busy || Boolean(resource.error)}
              onClick={() => openEditor("task")}
            >
              New task
            </button>
          ) : view === "projects" ? (
            <button
              disabled={!token || busy || Boolean(resource.error)}
              onClick={() => openEditor("project")}
            >
              New project
            </button>
          ) : (
            <button
              disabled={
                !token || !calendar.data?.connected || Boolean(calendar.error)
              }
              onClick={() =>
                prepare(
                  "Create a calendar event. Ask me for its title, date, time, calendar account and confirmation before saving.",
                )
              }
            >
              Create through HANNI
            </button>
          )}
        </div>
      </header>
      {error && !editor && !confirmation && (
        <p className="feature-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="feature-note" role="status">
          {notice}
        </p>
      )}
      {resource.error && view !== "calendar" && (
        <p className="feature-error" role="status">
          {resource.error} {data && "Displayed records may be stale."}
        </p>
      )}
      {view === "calendar" ? (
        <>
          <div className="feature-toolbar">
            <input
              type="date"
              aria-label="Calendar start date"
              value={day}
              onChange={(event) => {
                setDay(event.target.value || today());
                setCalendarRevision(0);
              }}
            />
            <select
              aria-label="Calendar range"
              value={days}
              onChange={(event) => {
                setDays(Number(event.target.value));
                setCalendarRevision(0);
              }}
            >
              <option value={1}>Daily schedule</option>
              <option value={7}>Weekly schedule</option>
            </select>
            <button
              disabled={!token}
              onClick={() => setCalendarRevision((value) => value + 1)}
            >
              Refresh calendar
            </button>
            <span className="feature-note">
              {!calendar.data
                ? "Checking"
                : calendar.data.connected
                  ? "Connected"
                  : "Not connected"}
            </span>
          </div>
          {calendarList}
          <section
            className="calendar-deadlines"
            aria-label="Local task deadlines"
          >
            <div className="section-title">
              <h2>Local task deadlines</h2>
              <span>{calendarDeadlines.length} open in this range</span>
            </div>
            {resource.error && (
              <p className="feature-error" role="status">
                {resource.error} {data && "Displayed tasks may be stale."}
              </p>
            )}
            {!data ? (
              <p className="feature-empty">Loading saved tasks.</p>
            ) : !data.available ? (
              <p className="feature-empty">
                {data.reason || "Local tasks unavailable."}
              </p>
            ) : calendarDeadlines.length ? (
              calendarDeadlines.map((task) => (
                <div key={task.id}>
                  <time dateTime={task.due}>{dueLabel(task)}</time>
                  <button
                    className="text-link"
                    onClick={() => {
                      if (storeInspection("tasks", task.id)) navigate("tasks");
                      else
                        setError(
                          "Could not retain the task target. Open Tasks directly.",
                        );
                    }}
                  >
                    {task.title}
                  </button>
                  <span>{task.priority} priority</span>
                </div>
              ))
            ) : (
              <p className="feature-empty">
                No open local tasks are due in this range.
              </p>
            )}
            <button className="text-link" onClick={() => navigate("tasks")}>
              Open all tasks
            </button>
          </section>
        </>
      ) : !data ? (
        <div
          className="skeleton-group"
          role="status"
          aria-label="Loading workspace"
        >
          <span className="skeleton" />
          <span className="skeleton medium" />
        </div>
      ) : !data.available ? (
        <p className="feature-empty">
          {data.reason || "Workspace unavailable."}
        </p>
      ) : view === "projects" ? (
        <div className="project-layout">
          <section className="project-list" aria-label="Projects">
            {data.projects.length ? (
              data.projects.map((item) => (
                <button
                  key={item.id}
                  className={project === item.id ? "selected" : ""}
                  aria-pressed={project === item.id}
                  onClick={() => setProject(item.id)}
                >
                  <strong>{item.name}</strong>
                  <small>
                    {
                      data.tasks.filter(
                        (task) =>
                          task.project_id === item.id &&
                          task.status === "completed",
                      ).length
                    }{" "}
                    /{" "}
                    {
                      data.tasks.filter((task) => task.project_id === item.id)
                        .length
                    }{" "}
                    tasks complete
                  </small>
                </button>
              ))
            ) : (
              <p className="feature-empty">Create your first project.</p>
            )}
          </section>
          <section className="project-details">
            {selectedProject ? (
              <>
                <div className="section-title">
                  <h2>{selectedProject.name}</h2>
                  <div>
                    <button
                      className="text-link"
                      onClick={() => openEditor("project", selectedProject)}
                    >
                      Edit project
                    </button>
                    <button
                      className="text-link"
                      onClick={() => {
                        pending.current = null;
                        setConfirmation({
                          operation: "project.delete",
                          data: {
                            project_id: selectedProject.id,
                            expected_fingerprint: selectedProject.fingerprint,
                          },
                          title: `Delete ${selectedProject.name}?`,
                          description:
                            "The project, its notes and saved links will be removed. Its tasks remain in your task list.",
                        });
                      }}
                    >
                      Delete project
                    </button>
                  </div>
                </div>
                {selectedProject.description && (
                  <p className="project-description">
                    {selectedProject.description}
                  </p>
                )}
                <div className="section-title">
                  <h2>Tasks</h2>
                  <button
                    className="text-link"
                    onClick={() => openEditor("task")}
                  >
                    Add task
                  </button>
                </div>
                {taskList}
                <div className="section-title">
                  <h2>Notes</h2>
                  <button
                    className="text-link"
                    onClick={() => openEditor("note")}
                  >
                    Add note
                  </button>
                </div>
                {data.notes
                  .filter((note) => note.project_id === project)
                  .map((note) => (
                    <details className="project-note" key={note.id}>
                      <summary>
                        {note.title}
                        <time>
                          {new Date(note.updated_at).toLocaleDateString()}
                        </time>
                      </summary>
                      <p>{note.body || "No note body."}</p>
                      <button
                        className="text-link"
                        onClick={() => openEditor("note", note)}
                      >
                        Edit note
                      </button>
                      <button
                        className="text-link"
                        onClick={() => {
                          pending.current = null;
                          setConfirmation({
                            operation: "note.delete",
                            data: {
                              note_id: note.id,
                              expected_fingerprint: note.fingerprint,
                            },
                            title: `Delete ${note.title}?`,
                            description:
                              "This removes this saved project note.",
                          });
                        }}
                      >
                        Delete note
                      </button>
                    </details>
                  ))}
                {!data.notes.some((note) => note.project_id === project) && (
                  <p className="feature-note">
                    No project notes yet. These notes are separate from
                    assistant memory.
                  </p>
                )}
                <div className="section-title">
                  <h2>Related files &amp; conversation</h2>
                  <button
                    className="text-link"
                    onClick={() => openEditor("link")}
                  >
                    Add link
                  </button>
                </div>
                {data.links
                  .filter((link) => link.project_id === project)
                  .map((link) => (
                    <div className="project-link" key={link.id}>
                      <button
                        className="text-link"
                        onClick={() => {
                          if (link.kind === "file")
                            prepare(
                              `Open the file at ${link.target}. Use the existing file capability and its permission checks.`,
                            );
                          else {
                            if (storeInspection("chat", link.target))
                              navigate("chat");
                            else
                              setError(
                                "The message target could not be retained. Open Conversation and inspect its history.",
                              );
                          }
                        }}
                      >
                        {link.label}
                      </button>
                      <small>
                        {link.kind === "file"
                          ? link.target
                          : `Message ${link.target}`}
                      </small>
                      <button
                        className="text-link"
                        aria-label={`Remove ${link.label} link`}
                        onClick={() => {
                          pending.current = null;
                          setConfirmation({
                            operation: "link.delete",
                            data: { link_id: link.id },
                            title: `Remove ${link.label}?`,
                            description:
                              "Only the saved link is removed. The file or conversation is preserved.",
                          });
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
              </>
            ) : (
              <p className="feature-empty">
                Select a project to inspect its tasks, notes and links.
              </p>
            )}
          </section>
        </div>
      ) : (
        <>
          <div className="feature-toolbar">
            <input
              type="search"
              aria-label="Search tasks"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search tasks"
            />
            {view === "tasks" && (
              <select
                aria-label="Task status"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                <option value="open">Open tasks</option>
                <option value="completed">Completed tasks</option>
                <option value="all">All tasks</option>
              </select>
            )}
            <select
              aria-label="Task project"
              value={project}
              onChange={(event) => setProject(event.target.value)}
            >
              <option value="">All projects</option>
              {data.projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button className="text-link" onClick={resource.refresh}>
              Refresh tasks
            </button>
          </div>
          {view === "planner" ? (
            <div className="planner-columns">
              <section>
                <div className="section-title">
                  <h2>Needs attention</h2>
                  <span>Due today, overdue or unscheduled</span>
                </div>
                {taskList}
              </section>
              <section>
                <div className="section-title">
                  <h2>Upcoming calendar</h2>
                  <button
                    className="text-link"
                    onClick={() => setCalendarRevision((value) => value + 1)}
                  >
                    Refresh
                  </button>
                </div>
                {calendarList}
                <button
                  className="text-link"
                  onClick={() => navigate("calendar")}
                >
                  Open calendar
                </button>
              </section>
            </div>
          ) : (
            taskList
          )}
          <div className="workspace-backup">
            <p className="feature-note">
              Tasks share HANNI's existing local task store. Create a backup
              before making important changes.
            </p>
            <button
              className="text-link"
              disabled={writeBlocked}
              onClick={() => execute("workspace.backup", {})}
            >
              Back up workspace
            </button>
          </div>
        </>
      )}
      {editor && (
        <FeatureDialog
          title={`${editor.id ? "Edit" : "New"} ${editor.kind}`}
          busy={busy}
          onClose={() => setEditor(null)}
        >
          <form className="workspace-form" onSubmit={save}>
            <label htmlFor="workspace-title">
              {editor.kind === "project"
                ? "Project name"
                : editor.kind === "link"
                  ? "Link label"
                  : "Title"}
            </label>
            <input
              autoFocus
              id="workspace-title"
              maxLength={editor.kind === "task" ? 300 : 200}
              value={form.title}
              required
              disabled={busy}
              onChange={(event) =>
                setForm({ ...form, title: event.target.value })
              }
            />
            {editor.kind === "task" && (
              <>
                <label htmlFor="workspace-due">Due date (optional)</label>
                <input
                  id="workspace-due"
                  type="date"
                  value={form.due}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, due: event.target.value })
                  }
                />
                <label htmlFor="workspace-priority">Priority</label>
                <select
                  id="workspace-priority"
                  value={form.priority}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, priority: event.target.value })
                  }
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                </select>
                <label htmlFor="workspace-course">Course or category</label>
                <input
                  id="workspace-course"
                  maxLength={120}
                  value={form.course}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, course: event.target.value })
                  }
                />
                <label htmlFor="workspace-project">Project</label>
                <select
                  id="workspace-project"
                  value={form.project_id}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, project_id: event.target.value })
                  }
                >
                  <option value="">No project</option>
                  {data?.projects.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                {editor.id && (
                  <>
                    <label htmlFor="workspace-status">Status</label>
                    <select
                      id="workspace-status"
                      value={form.status}
                      disabled={busy}
                      onChange={(event) =>
                        setForm({ ...form, status: event.target.value })
                      }
                    >
                      <option value="open">Open</option>
                      <option value="completed">Completed</option>
                    </select>
                  </>
                )}
              </>
            )}
            {(editor.kind === "project" || editor.kind === "note") && (
              <>
                <label htmlFor="workspace-body">
                  {editor.kind === "note" ? "Note" : "Description"}
                </label>
                <textarea
                  id="workspace-body"
                  rows={5}
                  maxLength={4000}
                  value={form.body}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, body: event.target.value })
                  }
                />
              </>
            )}
            {editor.kind === "link" && (
              <>
                <label htmlFor="workspace-link-kind">Link type</label>
                <select
                  id="workspace-link-kind"
                  value={form.kind}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, kind: event.target.value })
                  }
                >
                  <option value="file">File path</option>
                  <option value="conversation">Conversation message</option>
                </select>
                <label htmlFor="workspace-target">
                  {form.kind === "file" ? "Absolute file path" : "Message ID"}
                </label>
                <input
                  id="workspace-target"
                  value={form.target}
                  required
                  maxLength={2000}
                  disabled={busy}
                  onChange={(event) =>
                    setForm({ ...form, target: event.target.value })
                  }
                />
                <p className="feature-note">
                  File access goes through HANNI's controller when you open the
                  link.
                </p>
              </>
            )}
            {error && (
              <p className="feature-error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditor(null)}
              >
                Cancel
              </button>
              <button type="submit" disabled={writeBlocked}>
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </FeatureDialog>
      )}
      {confirmation && (
        <FeatureDialog
          title={confirmation.title}
          busy={busy}
          onClose={() => setConfirmation(null)}
        >
          <p className="confirmation-copy">{confirmation.description}</p>
          {error && (
            <p className="feature-error" role="alert">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              autoFocus
              disabled={busy}
              onClick={() => setConfirmation(null)}
            >
              Cancel
            </button>
            <button
              className="danger-button"
              disabled={writeBlocked}
              onClick={async () => {
                if (await execute(confirmation.operation, confirmation.data))
                  setConfirmation(null);
              }}
            >
              {busy ? "Removing…" : "Confirm deletion"}
            </button>
          </div>
        </FeatureDialog>
      )}
    </div>
  );
}
