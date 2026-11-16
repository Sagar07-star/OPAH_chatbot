import { BadgeCheck, MapPin, Plus, Star, UserRound } from "lucide-react";
import { titleCase } from "../../services/format";
import { money } from "../../services/format";
import type { Talent } from "../../types";
import { initials } from "../../services/format";

interface Props {
  talents: Talent[];
  count?: number;
  relaxed?: string[];
  roleNotice?: string | null;
  isClient: boolean;
  projectName: string | null;
  onPrompt: (text: string) => void;
  onOpenProfile: (talentId: string) => void;
}

export function TalentResultCards({
  talents,
  count,
  relaxed,
  roleNotice,
  isClient,
  projectName,
  onPrompt,
  onOpenProfile,
}: Props) {
  if (roleNotice) {
    return (
      <div className="rounded-xl border border-warning/25 bg-warning-soft px-3.5 py-2.5 text-[12px] text-warning">
        {roleNotice}
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="chip">{count ?? talents.length} matches</span>
        {relaxed?.map((note) => (
          <span key={note} className="chip border-warning/25 bg-warning-soft text-warning">
            {note}
          </span>
        ))}
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {talents.map((talent) => (
          <article
            key={talent.id}
            className="group overflow-hidden rounded-xl border border-line bg-surface shadow-card transition-shadow hover:shadow-lift"
          >
            <div className="relative h-28 w-full overflow-hidden bg-canvas">
              <span className="absolute inset-0 grid place-items-center text-[18px] font-semibold text-faint">
                {initials(talent.name)}
              </span>
              {talent.thumbnail ? (
                <img
                  src={talent.thumbnail}
                  alt=""
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  className="relative h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                  onError={(event) => {
                    event.currentTarget.style.display = "none";
                  }}
                />
              ) : null}
              <span className="absolute left-2 top-2 rounded-full border border-line/60 bg-surface/90 px-1.5 py-0.5 text-[10px] font-medium text-ink backdrop-blur">
                {talent.role}
              </span>
            </div>
            <div className="p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-[12.5px] font-semibold text-ink">{talent.name}</p>
                  <p className="mt-0.5 flex items-center gap-1 text-[10.5px] text-muted">
                    <MapPin size={9.5} />
                    {talent.city.replace(", FL", "")}
                    {talent.distance_miles ? ` · ${talent.distance_miles} mi` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[12.5px] font-semibold text-ink">{money(talent.day_rate)}</p>
                  <p className="text-[9.5px] text-faint">per day</p>
                </div>
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-[10.5px] text-muted">
                <span className="inline-flex items-center gap-0.5">
                  <Star size={9.5} className="fill-warning text-warning" />
                  {Number(talent.rating ?? 0).toFixed(1)}
                </span>
                <span className="text-faint">·</span>
                <span>{talent.experience_years}y experience</span>
              </div>
              <ul className="mt-2 space-y-0.5">
                {talent.match.reasons.slice(0, 2).map((reason) => (
                  <li key={reason} className="flex items-start gap-1 text-[10.5px] leading-snug text-muted">
                    <BadgeCheck size={10} className="mt-0.5 flex-none text-accent" />
                    {reason}
                  </li>
                ))}
              </ul>
              {talent.styles.length > 0 ? (
                <p className="mt-1.5 truncate text-[10px] text-faint">{talent.styles.map(titleCase).join(" · ")}</p>
              ) : null}
              <div className="mt-2.5 flex gap-1.5">
                <button className="btn flex-1 px-2 py-1 text-[11.5px]" onClick={() => onOpenProfile(talent.id)}>
                  <UserRound size={11.5} /> Profile
                </button>
                {isClient ? (
                  <button
                    className="btn btn-primary flex-1 px-2 py-1 text-[11.5px]"
                    onClick={() =>
                      onPrompt(
                        `Add ${talent.name} (${talent.id}) to ${projectName ?? "my project"}`,
                      )
                    }
                  >
                    <Plus size={11.5} /> Add
                  </button>
                ) : null}
              </div>
            </div>
          </article>
        ))}
      </div>
      {!isClient ? (
        <p className="text-[10.5px] text-faint">
          Sign in with a demo client to see profiles and invite a creative.
        </p>
      ) : null}
    </div>
  );
}
