import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Upload, X } from "lucide-react";
import { cn } from "@/utils/cn";

interface FileUploadZoneProps {
  label: string;
  accept: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
}

export function FileUploadZone({ label, accept, file, onFileChange }: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function handleDrag(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFileChange(dropped);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    onFileChange(f);
  }

  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-400">{label}</label>
      {file ? (
        <div className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-300">
          <span className="flex-1 truncate">{file.name}</span>
          <button
            type="button"
            onClick={() => onFileChange(null)}
            className="text-slate-500 hover:text-slate-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed py-4 transition-colors",
            dragActive
              ? "border-brand-400/50 bg-brand-500/10"
              : "border-white/10 hover:border-white/20",
          )}
        >
          <Upload className="h-5 w-5 text-slate-500" />
          <span className="text-xs text-slate-500">Drop file or click to browse</span>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleChange}
            className="hidden"
          />
        </div>
      )}
    </div>
  );
}
