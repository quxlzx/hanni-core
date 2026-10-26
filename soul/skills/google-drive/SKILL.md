---
name: google-drive
description: Find files and recent work in connected Google Drive accounts, disambiguate similar results, and return verified file links and metadata.
metadata:
  hanni:
    triggers: [google drive, in drive, my drive, work drive, school drive, drive files, drive documents, recent drive, find my resume]
---

# Find work in Google Drive

Keep searches in the user's selected or default account. Use
`google.drive.search` for a name or topic, `.recent` for recently modified work,
and `.metadata` for an exact file ID returned by a prior lookup. Supply a bounded
limit; `docs_only` narrows results to native Google Docs when that is intended.

Show a short selection with file name, type, modified time, account and verified
web URL. When names repeat, use these fields to distinguish the files. Keep the
file ID tied to its account. If multiple files could be "the report," ask the
user to choose instead of silently taking the newest. Truncated results are a
partial search, not proof that other files do not exist.

Search results are metadata, not file content. Use `google.docs.read` only for
native Google Docs whose content the user wants read. For PDFs, Excel files,
Google Sheets or Slides, provide the returned link; if analysis is needed, the
user can export or attach a supported document to HANNI. This integration does
not download arbitrary Drive files or edit Sheets and Slides.

Return the verified URL when asked to open a file; the Drive tool itself does not
launch a browser. Sharing, deletion, folder organization and document edits are
unsupported. Do not substitute local file operations for a Drive change.
