export type Attachment = {
  id: string;
  name: string;
  size: number;
  media_type: string;
  characters: number;
  truncated: boolean;
};

export const MAX_FILE_BYTES = 8 * 1024 * 1024;
export const MAX_FILES = 5;
export const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.gif,.bmp";
export const isImage = (file: { name: string; media_type?: string }) => file.media_type?.startsWith("image/") || IMAGE_ACCEPT.split(",").includes(file.name.slice(file.name.lastIndexOf(".")).toLowerCase());
export const FILE_ACCEPT = ".pdf,.docx,.pptx,.odt,.xlsx,.xlsm,.xls,.ods,.txt,.md,.markdown,.csv,.tsv,.json,.jsonl,.xml,.yaml,.yml,.log,.py,.js,.jsx,.ts,.tsx,.html,.htm,.css,.sql,.sh,.ps1,.toml,.ini,.cfg,.rst,.tex,.c,.h,.cpp,.hpp,.cs,.java,.go,.rs,.rb,.php,.swift,.kt,.r,.ipynb";

export function validateFile(file: { name: string; size: number }): string {
  if (!file.name || file.name.length > 200 || /[\u0000-\u001f\u007f/\\]/.test(file.name))
    return "Choose a file with a valid filename (maximum 200 characters).";
  if (file.size <= 0) return `${file.name} is empty. Choose a file with content.`;
  if (file.size > MAX_FILE_BYTES) return `${file.name} exceeds 8 MiB. Choose a smaller file.`;
  const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (![...FILE_ACCEPT.split(","), ...IMAGE_ACCEPT.split(",")].includes(suffix))
    return "Choose an image (PNG, JPEG, WebP, GIF, BMP), PDF, Office document, HTML, text, CSV, JSON, or code file.";
  return "";
}

export function fileSize(size: number): string {
  return size < 1024 ? `${size} B` : size < 1024 * 1024
    ? `${Math.ceil(size / 1024)} KiB` : `${(size / (1024 * 1024)).toFixed(1)} MiB`;
}

export function sameFiles(first: string[] = [], second: string[] = []): boolean {
  return first.length === second.length && [...first].sort().every((id, i) => id === [...second].sort()[i]);
}

export function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new Error(`Could not read ${file.name}. Select it again.`));
    reader.readAsDataURL(file);
  });
}

export function clipboardImages(data: Pick<DataTransfer, "items" | "files">): File[] {
  const items = Array.from(data.items || []).filter(item => item.kind === "file" && item.type.startsWith("image/"))
    .map(item => item.getAsFile()).filter((file): file is File => Boolean(file));
  const files = items.length ? items : Array.from(data.files || []).filter(file => file.type.startsWith("image/"));
  const extensions: Record<string, string> = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/bmp": "bmp" };
  return files.map((file, index) => {
    if (isImage(file) || !extensions[file.type]) return file;
    return new File([file], `pasted-image-${index + 1}.${extensions[file.type]}`, { type: file.type });
  });
}

export function hasFileDrag(data: Pick<DataTransfer, "types" | "items">): boolean {
  return Array.from(data.types || []).includes("Files") || Array.from(data.items || []).some(item => item.kind === "file");
}

export function droppedFiles(data: Pick<DataTransfer, "items" | "files">): { files: File[]; error: string } {
  const items = Array.from(data.items || []).filter(item => item.kind === "file");
  if (items.some(item => item.webkitGetAsEntry?.()?.isDirectory))
    return { files: [], error: "Folders cannot be attached. Open the folder and drag the files you want to share." };
  const files = Array.from(data.files || []);
  return { files, error: files.length ? "" : "No files were received. Drag files from your file manager or paste a copied image." };
}
