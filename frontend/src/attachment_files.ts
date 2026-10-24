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
export const FILE_ACCEPT = ".pdf,.docx,.txt,.md,.markdown,.csv,.tsv,.json,.jsonl,.xml,.yaml,.yml,.log,.py,.js,.jsx,.ts,.tsx,.html,.css,.sql,.sh,.ps1,.toml,.ini,.cfg,.rst,.tex,.c,.h,.cpp,.hpp,.cs,.java,.go,.rs,.rb,.php,.swift,.kt,.r,.ipynb";

export function validateFile(file: { name: string; size: number }): string {
  if (!file.name || file.name.length > 200 || /[\u0000-\u001f\u007f/\\]/.test(file.name))
    return "Choose a file with a valid filename (maximum 200 characters).";
  if (file.size <= 0) return `${file.name} is empty. Choose a file with content.`;
  if (file.size > MAX_FILE_BYTES) return `${file.name} exceeds 8 MiB. Choose a smaller file.`;
  const suffix = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!FILE_ACCEPT.split(",").includes(suffix))
    return "Choose a PDF, DOCX, text, CSV, JSON, or source-code file.";
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
