import { useRef, useState } from "react";
import { localFetch, write } from "./api";
import { FILE_ACCEPT, MAX_FILES, fileSize, readFile, validateFile, type Attachment } from "./attachment_files";

type DraftFile = {
  id: string; name: string; size: number; file?: File;
  status: "uploading" | "ready" | "failed" | "removing";
  attachment?: Attachment; error?: string;
};

export function useChatFiles(conversation: string, token: string) {
  const [drafts, setDrafts] = useState<Record<string, DraftFile[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const current = useRef(drafts);
  const settled = useRef(new Set<string>());
  function update(id: string, change: (files: DraftFile[]) => DraftFile[]) {
    const next = { ...current.current, [id]: change(current.current[id] || []) };
    current.current = next;
    setDrafts(next);
  }
  async function upload(entry: DraftFile, owner: string) {
    if (!entry.file) return;
    update(owner, files => files.map(f => f.id === entry.id ? { ...f, status: "uploading", error: "" } : f));
    try {
      const attachment = await write<Attachment>("/api/chat/files", token, {
        operation: "add", id: entry.id, conversation: owner, name: entry.name, data: await readFile(entry.file),
      });
      update(owner, files => files.map(f => f.id === entry.id ? { ...f, status: "ready", attachment } : f));
    } catch (error) {
      update(owner, files => files.map(f => f.id === entry.id ? { ...f, status: "failed", error: error instanceof Error ? error.message : "Upload failed. Try again." } : f));
    }
  }
  async function add(input: FileList | File[]) {
    const files = Array.from(input);
    const existing = current.current[conversation] || [];
    setErrors(value => ({ ...value, [conversation]: "" }));
    if (existing.length + files.length > MAX_FILES) {
      setErrors(value => ({ ...value, [conversation]: "Attach up to five files. Remove a file before adding more." }));
      return;
    }
    const invalid = files.map(validateFile).find(Boolean);
    if (invalid) {
      setErrors(value => ({ ...value, [conversation]: invalid }));
      return;
    }
    const entries: DraftFile[] = files.map(file => ({ id: crypto.randomUUID(), name: file.name, size: file.size, file, status: "uploading" }));
    update(conversation, value => [...value, ...entries]);
    for (const entry of entries) await upload(entry, conversation);
  }
  async function remove(id: string) {
    const owner = conversation;
    const previous = current.current[owner]?.find(file => file.id === id);
    if (!previous || previous.status === "uploading" || previous.status === "removing") return;
    update(owner, files => files.map(file => file.id === id ? { ...file, status: "removing" } : file));
    try {
      await write("/api/chat/files", token, { operation: "remove", id, conversation: owner });
      settled.current.add(id);
      update(owner, files => files.filter(file => file.id !== id));
      setErrors(value => ({ ...value, [owner]: "" }));
    } catch (error) {
      update(owner, files => files.map(file => file.id === id ? { ...previous, error: error instanceof Error ? error.message : "Could not remove file. Try again." } : file));
    }
  }
  const files = drafts[conversation] || [];
  return { files, error: errors[conversation] || "", add, remove,
    retry: (entry: DraftFile) => upload(entry, conversation),
    clear: (owner: string, sent: string[]) => {
      sent.forEach(id => settled.current.add(id));
      update(owner, items => items.filter(file => !sent.includes(file.id)));
    },
    restore: (owner: string, saved: Attachment[]) => {
      const additions = saved.filter(file => !settled.current.has(file.id) && !current.current[owner]?.some(existing => existing.id === file.id));
      if (additions.length) update(owner, items => [...items, ...additions.map(attachment => ({ id: attachment.id, name: attachment.name, size: attachment.size, attachment, status: "ready" as const }))]);
    },
    ready: files.every(file => file.status === "ready" && !file.error),
    ids: files.filter(file => file.status === "ready").map(file => file.id),
  };
}

function FileIcon() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 3H5v18h14V8Z" /><path d="M14 3v6h5M8 13h8M8 17h5" /></svg>;
}

export function FilePicker({ disabled, add }: { disabled: boolean; add: (files: FileList) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <>
    <input ref={input} type="file" multiple accept={FILE_ACCEPT} hidden aria-label="Choose files to attach" onChange={event => {
      if (event.target.files) add(event.target.files);
      event.target.value = "";
    }} />
    <button type="button" className="hc-icon hc-attach-button" aria-label="Add files" title="Add files · PDF, DOCX, text or code · up to 5 files, 8 MiB each" disabled={disabled} onClick={() => input.current?.click()}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m8 12 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8M7 13l7-7" /></svg>
    </button>
  </>;
}

export function DraftFiles({ state, disabled }: { state: ReturnType<typeof useChatFiles>; disabled: boolean }) {
  return <>
    {state.files.length > 0 && <ul className="hc-files hc-draft-files" aria-label="Attached files">
      {state.files.map(file => <li key={file.id} className={file.error ? "has-error" : ""}>
        <div className="hc-file-main"><FileIcon /><span><strong title={file.name}>{file.name}</strong><small role="status">{file.error || (file.status === "uploading" ? "Uploading…" : file.status === "removing" ? "Removing…" : `${fileSize(file.size)} · ${file.attachment?.characters.toLocaleString()} characters`)}{file.attachment?.truncated && !file.error ? " · text excerpt" : ""}</small></span></div>
        {file.status === "failed" && <button type="button" className="hc-file-retry" disabled={disabled} onClick={() => state.retry(file)}>Retry</button>}
        <button type="button" className="hc-file-remove" aria-label={`Remove ${file.name}`} title={`Remove ${file.name}`} disabled={disabled || file.status === "uploading" || file.status === "removing"} onClick={() => state.remove(file.id)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="m7 7 10 10M7 17 17 7" /></svg></button>
      </li>)}
    </ul>}
    {state.error && <p className="hc-file-error" role="alert">{state.error}</p>}
  </>;
}

export function MessageFiles({ files, token, conversation }: { files: Attachment[]; token: string; conversation: string }) {
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState("");
  async function download(file: Attachment) {
    setError(""); setDownloading(file.id);
    try {
      const response = await localFetch(`/api/chat/file?id=${encodeURIComponent(file.id)}&conversation=${encodeURIComponent(conversation)}`, { headers: { "X-Hanni-Token": token }, cache: "no-store", signal: AbortSignal.timeout(20000) });
      if (!response.ok) throw new Error("File unavailable. Reload the conversation and try again.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = file.name;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "File could not be downloaded."); }
    finally { setDownloading(""); }
  }
  if (!files.length) return null;
  return <div className="hc-saved-files"><ul className="hc-files" aria-label="Message files">{files.map(file => <li key={file.id}>
    <button type="button" className="hc-file-main hc-file-download" disabled={!token || Boolean(downloading)} onClick={() => download(file)} title={`Download ${file.name}. Long documents may be excerpted for model context.`}><FileIcon /><span><strong>{file.name}</strong><small>{downloading === file.id ? "Downloading…" : `${fileSize(file.size)} · Download`}{file.truncated ? " · text excerpt" : ""}</small></span></button>
  </li>)}</ul>{error && <p className="hc-file-error" role="alert">{error}</p>}</div>;
}
