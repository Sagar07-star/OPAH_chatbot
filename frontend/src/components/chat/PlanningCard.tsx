import { Check, ChevronDown, FileText, Loader2, Save } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../../services/api";
import { titleCase } from "../../services/format";
import type { PlanningDoc } from "../../types";
import { Markdown } from "../Markdown";

interface Props {
  planning: PlanningDoc;
  projectId: string | null;
  projectName: string | null;
  canSave: boolean;
  saveHint?: string;
}

export function PlanningCard({ planning, projectId, projectName, canSave, saveHint }: Props) {
  const [expanded, setExpanded] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedVersion, setSavedVersion] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!projectId || saving) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.saveDocument(projectId, planning);
      setSavedVersion(result.document.version);
      window.dispatchEvent(new CustomEvent("createchat:data-changed"));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The document couldn't be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex items-start justify-between gap-2 border-b border-line bg-canvas/60 px-3.5 py-2.5">
        <div className="flex min-w-0 items-start gap-2">
          <span className="mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-md border border-line bg-surface text-muted">
            <FileText size={13} />
          </span>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
              {titleCase(planning.type)}
            </p>
            <p className="mt-0.5 text-[13px] font-medium leading-snug text-ink">{planning.title}</p>
            {projectName ? <p className="mt-0.5 text-[11px] text-muted">{projectName}</p> : null}
          </div>
        </div>
        <button
          className="btn btn-ghost px-1.5 py-1"
          onClick={() => setExpanded((value) => !value)}
          aria-label={expanded ? "Collapse document" : "Expand document"}
        >
          <ChevronDown size={14} className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
        </button>
      </div>

      {expanded ? (
        <div className="max-h-72 overflow-y-auto px-3.5 py-3 scroll-area">
          <Markdown text={planning.content_md} />
        </div>
      ) : null}

      <div className="border-t border-line px-3.5 py-2.5">
        {savedVersion ? (
          <p className="flex items-center gap-1.5 text-[11.5px] text-accent-ink">
            <Check size={12} /> Saved to {projectName ?? "the project"} · version {savedVersion}
          </p>
        ) : canSave ? (
          <button className="btn btn-accent w-full justify-center py-1.5" onClick={() => void save()} disabled={saving}>
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? "Saving…" : "Save to project"}
          </button>
        ) : (
          <p className="text-[11px] text-muted">{saveHint ?? "Pick a project to save this document."}</p>
        )}
        {error ? <p className="mt-1.5 text-[11px] text-danger">{error}</p> : null}
        <p className="mt-1.5 text-[10px] text-faint">
          Drafted by CREATEchat. Saving uses your own tap, not the model.
        </p>
      </div>
    </div>
  );
}
