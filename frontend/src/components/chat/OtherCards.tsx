import {
  AlertTriangle,
  Check,
  CircleDollarSign,
  Folder,
  Info,
  MessageSquare,
  Package as PackageIcon,
  Star,
  Ticket,
  Wrench,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  attentionTone,
  formatDate,
  formatTime,
  money,
  reviewLabel,
  titleCase,
} from "../../services/format";
import type {
  AccountSummary,
  Board,
  CancellationPreview,
  Card,
  DeliverableFolder,
  Package,
  ProjectDetail,
  ProjectSummary,
  SupportTicket,
} from "../../types";
import { StatusBadge } from "../ui";

function SectionTitle({ children }: { children: ReactNode }) {
  return <p className="eyebrow mb-1.5">{children}</p>;
}

export function AccountSummaryPanel({ summary }: { summary: AccountSummary }) {
  const attention = summary.needs_attention.slice(0, 6);
  return (
    <div className="space-y-3.5 rounded-xl border border-line bg-surface p-3.5 shadow-card">
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Upcoming", value: summary.upcoming_shoots.length },
          { label: "Attention", value: summary.needs_attention.length },
          {
            label: "Projects",
            value:
              summary.totals?.projects ??
              summary.projects?.length ??
              Object.values(summary.project_counts ?? {}).reduce((sum, count) => sum + (count ?? 0), 0),
          },
        ].map((item) => (
          <div key={item.label} className="rounded-lg border border-line bg-canvas px-2 py-1.5 text-center">
            <p className="text-[16px] font-semibold leading-none text-ink">{item.value}</p>
            <p className="mt-1 text-[9.5px] uppercase tracking-[0.1em] text-faint">{item.label}</p>
          </div>
        ))}
      </div>

      <div>
        <SectionTitle>Needs attention</SectionTitle>
        {attention.length === 0 ? (
          <p className="text-[11.5px] text-muted">Nothing is waiting on you right now.</p>
        ) : (
          <ul className="space-y-1">
            {attention.map((item, index) => {
              const tone = attentionTone(item.kind);
              return (
                <li key={`${item.kind}-${index}`} className="flex items-start gap-1.5">
                  <span className={`mt-0.5 flex-none rounded border px-1 py-0.5 text-[9px] font-medium ${tone.tone}`}>
                    {tone.label}
                  </span>
                  <span className="min-w-0 text-[11px] leading-snug text-muted">
                    {item.project ? <span className="font-medium text-ink">{item.project}</span> : null}
                    {item.project ? " · " : ""}
                    {item.detail}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <SectionTitle>Upcoming shoots</SectionTitle>
        {summary.upcoming_shoots.length === 0 ? (
          <p className="text-[11.5px] text-muted">No paid shoots are scheduled ahead.</p>
        ) : (
          <ul className="space-y-1.5">
            {summary.upcoming_shoots.slice(0, 3).map((shoot) => (
              <li key={shoot.id} className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <span className="block truncate text-[11.5px] font-medium text-ink">{shoot.name}</span>
                  <p className="truncate text-[10px] text-faint">
                    {formatDate(shoot.start_date)} ·{" "}
                    {typeof shoot.location === "string" && shoot.location ? shoot.location : "Location not set"}
                  </p>
                </div>
                <StatusBadge status={shoot.status} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function ProjectDetailsPanel({ project }: { project: ProjectDetail }) {
  const fields: { label: string; value: string }[] = [
    { label: "Dates", value: project.start_date ? formatDate(project.start_date) : "Not set" },
    { label: "Call time", value: formatTime(project.scheduled_time) },
    { label: "Duration", value: project.duration_hours ? `${project.duration_hours} hours` : "Not set" },
    { label: "Budget", value: money(project.budget) },
    { label: "Role", value: project.role ? `${project.role}${project.specialty ? ` · ${project.specialty}` : ""}` : "Not set" },
    { label: "Location", value: project.display_location ?? "Not set" },
  ];
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="flex items-start justify-between gap-2 border-b border-line bg-canvas/60 px-3.5 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-ink">{project.name}</p>
          <p className="mt-0.5 text-[10.5px] text-muted">
            {project.source === "package" ? "Package booking" : "Custom project"} · {titleCase(project.project_type ?? "")}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-2 px-3.5 py-3">
        {fields.map((field) => (
          <div key={field.label}>
            <p className="text-[9.5px] uppercase tracking-[0.1em] text-faint">{field.label}</p>
            <p className="mt-0.5 text-[11.5px] text-ink">{field.value}</p>
          </div>
        ))}
      </div>
      {project.bookings.length > 0 ? (
        <div className="border-t border-line px-3.5 py-2">
          <SectionTitle>Creative</SectionTitle>
          {project.bookings.map((booking) => (
            <div key={booking.id} className="flex items-center justify-between gap-2 py-0.5">
              <span className="text-[11.5px] text-ink">
                {booking.talent_name} <span className="text-faint">· {booking.role}</span>
              </span>
              <span className="text-[10.5px] text-muted">{titleCase(booking.status)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {project.missing_fields?.length ? (
        <div className="border-t border-line bg-warning-soft/60 px-3.5 py-2">
          <p className="text-[10.5px] text-warning">
            Missing {project.missing_fields.map(titleCase).join(", ")}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function ProjectListPanel({ projects }: { projects: ProjectSummary[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <ul className="divide-y divide-line">
        {projects.map((project) => (
          <li key={project.id} className="flex items-center justify-between gap-2 px-3.5 py-2">
            <div className="min-w-0">
              <span className="block truncate text-[12px] font-medium text-ink">{project.name}</span>
              <p className="text-[10px] text-faint">
                {formatDate(project.start_date)} · {money(project.budget)}
              </p>
            </div>
            <StatusBadge status={project.status} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DeliverablesPanel({ folders }: { folders: DeliverableFolder[] }) {
  return (
    <div className="space-y-2">
      {folders.map((folder) => (
        <div key={folder.id} className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
          <div className="flex items-start justify-between gap-2 px-3.5 py-2.5">
            <div className="min-w-0">
              <p className="text-[12.5px] font-medium text-ink">{folder.name}</p>
              <p className="mt-0.5 text-[10.5px] text-muted">
                {folder.files?.length ?? folder.file_count ?? 0} files
                {folder.review_due_at ? ` · review closes ${formatDate(folder.review_due_at)}` : ""}
              </p>
            </div>
            <span className="chip">{reviewLabel(folder.review_status)}</span>
          </div>
          {folder.files && folder.files.length > 0 ? (
            <div className="grid grid-cols-3 gap-1 px-3.5 pb-3">
              {folder.files.slice(0, 3).map((file) => (
                <div key={file.id} className="overflow-hidden rounded-md border border-line bg-canvas">
                  {file.preview_url ? (
                    <img
                      src={file.preview_url}
                      alt={file.name}
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      className="h-16 w-full object-cover"
                    />
                  ) : (
                    <div className="grid h-16 place-items-center text-faint">
                      <Folder size={14} />
                    </div>
                  )}
                  <p className="truncate px-1 py-0.5 text-[9px] text-muted">{file.name}</p>
                </div>
              ))}
            </div>
          ) : null}
          {folder.revision_note ? (
            <p className="border-t border-line px-3.5 py-1.5 text-[10.5px] text-muted">
              Revision note: {folder.revision_note}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function MessagesPanel({ messages }: { messages: { id: string; sender: string; text: string; sent_at: string }[] }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3 shadow-card">
      <div className="mb-2 flex items-center gap-1.5">
        <MessageSquare size={12} className="text-muted" />
        <p className="text-[10.5px] font-medium text-muted">Project conversation</p>
      </div>
      <ul className="space-y-2">
        {messages.map((message) => (
          <li key={message.id} className={`flex ${message.sender === "client" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-lg px-2.5 py-1.5 text-[11.5px] leading-relaxed ${
                message.sender === "client" ? "bg-ink text-white" : "border border-line bg-canvas text-ink"
              }`}
            >
              {message.text}
              <span className={`mt-1 block text-[9px] ${message.sender === "client" ? "text-white/50" : "text-faint"}`}>
                {message.sender === "client" ? "You" : "Creative"} · {formatDate(message.sent_at)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PackagesPanel({ packages, onPrompt, isClient }: { packages: Package[]; onPrompt: (text: string) => void; isClient: boolean }) {
  return (
    <div className="space-y-2">
      {packages.map((pkg) => (
        <div key={pkg.id} className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink">
                <PackageIcon size={12} className="text-muted" />
                {pkg.title}
              </p>
              <p className="mt-0.5 text-[10.5px] text-muted">
                {pkg.duration} · {pkg.role}
              </p>
            </div>
            <p className="text-[13px] font-semibold text-ink">{money(pkg.price)}</p>
          </div>
          <ul className="mt-1.5 space-y-0.5">
            {[...pkg.deliverables, ...pkg.includes].slice(0, 3).map((item) => (
              <li key={item} className="flex items-start gap-1 text-[10.5px] text-muted">
                <Check size={10} className="mt-0.5 flex-none text-accent" /> {item}
              </li>
            ))}
          </ul>
          {pkg.add_ons.length ? (
            <p className="mt-1 text-[10px] text-faint">
              Add-ons: {pkg.add_ons.map((addon) => `${addon.label} ${money(addon.price)}`).join(" · ")}
            </p>
          ) : null}
          {isClient ? (
            <button
              className="btn mt-2 w-full justify-center py-1 text-[11px]"
              onClick={() => onPrompt(`I'm interested in the ${pkg.title} package — can you prepare the booking?`)}
            >
              Ask about this package
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function BoardsPanel({ boards }: { boards: Board[] }) {
  return (
    <div className="space-y-2">
      {boards.map((board) => (
        <div key={board.id} className="rounded-xl border border-line bg-surface p-3 shadow-card">
          <div className="flex items-center justify-between">
            <p className="text-[12px] font-medium text-ink">{board.title}</p>
            <span className="chip">{board.items.length} items</span>
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1">
            {board.items.slice(0, 8).map((item) => (
              <img
                key={item.id}
                src={item.url}
                alt={item.note ?? ""}
                loading="lazy"
                referrerPolicy="no-referrer"
                className="h-12 w-full rounded border border-line object-cover"
                onError={(event) => {
                  event.currentTarget.style.visibility = "hidden";
                }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DiagnosisPanel({ diagnosis }: { diagnosis: NonNullable<Card["diagnosis"]> }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
      <p className="flex items-center gap-1.5 text-[11px] font-medium text-ink">
        <Wrench size={12} className="text-muted" /> Account facts · {titleCase(diagnosis.topic)}
      </p>
      <ul className="mt-2 space-y-1">
        {diagnosis.facts.map((fact, index) => (
          <li key={index} className="flex items-start gap-1.5 text-[11px] leading-snug text-muted">
            <Info size={10} className="mt-0.5 flex-none text-faint" />
            {fact}
          </li>
        ))}
      </ul>
      {diagnosis.fixes.length ? (
        <>
          <p className="mt-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">Try this</p>
          <ul className="mt-1 space-y-0.5">
            {diagnosis.fixes.map((fix) => (
              <li key={fix} className="flex items-start gap-1.5 text-[11px] leading-snug text-ink">
                <Check size={10} className="mt-0.5 flex-none text-accent" /> {fix}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {diagnosis.stub ? (
        <p className="mt-2 flex items-start gap-1.5 rounded border border-warning/25 bg-warning-soft px-2 py-1 text-[10px] text-warning">
          <AlertTriangle size={10} className="mt-0.5 flex-none" />
          Part of this topic is a prototype stub, not a connected OPAH setting.
        </p>
      ) : null}
    </div>
  );
}

export function SupportTicketsPanel({ tickets, note }: { tickets: SupportTicket[]; note?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-ink">
        <Ticket size={12} className="text-muted" /> Support tickets
      </p>
      {tickets.length === 0 ? (
        <p className="text-[11px] text-muted">No tickets on this account.</p>
      ) : (
        <ul className="space-y-1.5">
          {tickets.map((ticket) => (
            <li key={ticket.id} className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-[11.5px] text-ink">{ticket.subject}</p>
                <p className="text-[9.5px] text-faint">
                  {ticket.id} · opened {formatDate(ticket.created_at)}
                </p>
              </div>
              <span className="chip flex-none">{ticket.status_label ?? titleCase(ticket.status)}</span>
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="mt-2 border-t border-line pt-1.5 text-[10px] text-faint">{note}</p> : null}
    </div>
  );
}

export function TicketCreatedPanel({ ticket, note }: { ticket?: SupportTicket; note?: string }) {
  return (
    <div className="rounded-xl border border-warning/25 bg-warning-soft px-3.5 py-2.5">
      <p className="flex items-center gap-1.5 text-[11.5px] font-medium text-warning">
        <Ticket size={12} /> Ticket queued in the prototype
      </p>
      {ticket ? (
        <p className="mt-1 text-[11px] text-warning">
          {ticket.id} · {ticket.subject}
        </p>
      ) : null}
      <p className="mt-1 text-[10px] leading-relaxed text-warning/90">
        {note ?? "No OPAH support system received this ticket."}
      </p>
    </div>
  );
}

export function StubNoticePanel({ title, message }: { title?: string; message?: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-line bg-canvas px-3.5 py-2.5">
      <AlertTriangle size={13} className="mt-0.5 flex-none text-muted" />
      <div>
        <p className="text-[11.5px] font-medium text-ink">{title ?? "Not connected"}</p>
        <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted">{message}</p>
      </div>
    </div>
  );
}

export function CancellationPanel({ preview }: { preview: CancellationPreview }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
      <p className="flex items-center gap-1.5 text-[11px] font-medium text-ink">
        <CircleDollarSign size={12} className="text-muted" /> If you cancel now
      </p>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-[20px] font-semibold leading-none text-ink">{money(preview.refund_amount)}</p>
        <p className="text-[11px] text-muted">
          {preview.refund_percent === null ? "Nothing paid yet" : `${preview.refund_percent}% refund`}
        </p>
      </div>
      <p className="mt-1 text-[10.5px] text-muted">
        {preview.message ??
          `${titleCase(preview.tier)} · ${preview.hours_until_start ?? "—"} hours until the shoot`}
      </p>
      <p className="mt-2 border-t border-line pt-1.5 text-[10px] text-faint">
        Preview only. Cancelling happens in the OPAH cancellation screen.
      </p>
    </div>
  );
}

export function OptionsPanel({ catalogs }: { catalogs: NonNullable<Card["catalogs"]> }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-3.5 shadow-card">
      <p className="mb-2 text-[11px] font-medium text-ink">Available option codes</p>
      <div className="space-y-2">
        {Object.entries(catalogs).map(([key, catalog]) => (
          <details key={key} className="rounded-lg border border-line bg-canvas px-2.5 py-1.5">
            <summary className="cursor-pointer text-[11px] font-medium text-ink">
              {catalog.label} <span className="font-normal text-faint">({catalog.options.length})</span>
            </summary>
            <p className="mt-1 text-[10px] leading-relaxed text-muted">
              {catalog.options.map((option) => option.label).join(" · ")}
            </p>
          </details>
        ))}
      </div>
    </div>
  );
}

export function ReviewStars({ rating }: { rating: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((value) => (
        <Star key={value} size={10} className={value <= rating ? "fill-warning text-warning" : "text-line-strong"} />
      ))}
    </span>
  );
}

