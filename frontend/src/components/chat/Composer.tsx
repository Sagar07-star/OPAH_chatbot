import { ArrowUp, Loader2, Paperclip, Square, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { fileSize } from "../../services/format";
import type { UploadRecord } from "../../types";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  sending: boolean;
  uploads: UploadRecord[];
  onFiles: (files: FileList | null) => void;
  onRemoveUpload: (id: string) => void;
  uploading: boolean;
  disabled?: boolean;
  placeholder: string;
  hint?: string;
}

export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  sending,
  uploads,
  onFiles,
  onRemoveUpload,
  uploading,
  disabled,
  placeholder,
  hint,
}: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const node = textarea.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 148)}px`;
  }, [value]);

  const canSend = !sending && !uploading && !disabled && (value.trim().length > 0 || uploads.length > 0);

  return (
    <div>
      {uploads.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {uploads.map((upload) => (
            <span
              key={upload.id}
              className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-line bg-surface px-2 py-1 text-[10.5px] text-body"
            >
              <Paperclip size={10} className="flex-none text-faint" />
              <span className="truncate">{upload.filename}</span>
              <span className="flex-none text-faint">{fileSize(upload.size_bytes)}</span>
              <button
                className="flex-none rounded p-0.5 text-faint hover:bg-canvas hover:text-ink"
                onClick={() => onRemoveUpload(upload.id)}
                aria-label={`Remove ${upload.filename}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="rounded-2xl border border-line bg-surface p-2 shadow-card transition-colors focus-within:border-accent-ring">
        <textarea
          ref={textarea}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (canSend) onSend();
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          className="max-h-[148px] w-full resize-none border-0 bg-transparent px-2 py-1.5 text-[13.5px] leading-relaxed text-ink placeholder:text-faint focus:outline-none disabled:opacity-60"
          aria-label="Message CREATEchat"
        />
        <div className="flex items-center justify-between gap-2 px-1">
          <div className="flex items-center gap-1">
            <button
              className="btn btn-ghost px-1.5 py-1 text-[11px]"
              onClick={() => input.current?.click()}
              disabled={sending || uploading || disabled}
              title="Attach a PDF or image"
              aria-label="Attach a file"
            >
              {uploading ? <Loader2 size={14} className="animate-spin" /> : <Paperclip size={14} />}
            </button>
            <input
              ref={input}
              type="file"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
              multiple
              onChange={(event) => {
                onFiles(event.target.files);
                event.target.value = "";
              }}
            />
            <span className="hidden text-[10px] text-faint sm:inline">
              {hint ?? "PDF or image · up to 10 files"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="hidden text-[9.5px] text-faint sm:inline">Enter to send · Shift+Enter new line</span>
            {sending ? (
              <button
                className="btn h-7 w-7 rounded-lg border-line-strong p-0"
                onClick={onStop}
                aria-label="Stop generating"
                title="Stop"
              >
                <Square size={11} className="fill-current" />
              </button>
            ) : (
              <button
                className="btn btn-primary h-7 w-7 rounded-lg p-0"
                onClick={onSend}
                disabled={!canSend}
                aria-label="Send message"
                title="Send"
              >
                <ArrowUp size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
