import { CalendarX2, Loader2, MapPin, Plus, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../services/api";
import { formatDate, money, titleCase } from "../services/format";
import type { TalentProfile } from "../types";
import { Modal } from "./ui";

interface Props {
  talentId: string | null;
  projectName: string | null;
  isClient: boolean;
  onClose: () => void;
  onPrompt: (text: string) => void;
}

export function TalentProfileModal({ talentId, projectName, isClient, onClose, onPrompt }: Props) {
  const [profile, setProfile] = useState<TalentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!talentId) return;
    setLoading(true);
    setError(null);
    setProfile(null);
    api
      .talentProfile(talentId)
      .then((result) => setProfile(result.talent))
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : "Could not load that profile."))
      .finally(() => setLoading(false));
  }, [talentId]);

  return (
    <Modal
      open={Boolean(talentId)}
      onClose={onClose}
      title={profile?.name ?? "Creative profile"}
      subtitle={profile ? `${profile.role} · ${profile.city.replace(", FL", "")}` : "Loading the profile"}
      width="max-w-2xl"
      footer={
        profile && isClient ? (
          <button
            className="btn btn-primary w-full justify-center"
            onClick={() => {
              onPrompt(`Add ${profile.name} (${profile.id}) to ${projectName ?? "my project"}`);
              onClose();
            }}
          >
            <Plus size={13} /> Ask CREATEchat to invite {profile.name.split(" ")[0]}
          </button>
        ) : (
          <p className="text-[11px] text-muted">
            {isClient ? "Profiles are read-only." : "Sign in with a demo client to invite a creative."}
          </p>
        )
      }
    >
      {loading ? (
        <div className="flex items-center gap-2 py-8 text-[12.5px] text-muted">
          <Loader2 size={14} className="animate-spin" /> Loading profile…
        </div>
      ) : null}
      {error ? <p className="py-6 text-[12.5px] text-danger">{error}</p> : null}
      {profile ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="inline-flex items-center gap-1 text-[12px] font-medium text-ink">
              <Star size={12} className="fill-warning text-warning" /> {profile.rating.toFixed(1)}
              <span className="font-normal text-faint">({profile.completed_projects} projects)</span>
            </span>
            <span className="inline-flex items-center gap-1 text-[12px] text-muted">
              <MapPin size={12} /> {profile.city}
            </span>
            <span className="text-[12px] font-semibold text-ink">{money(profile.day_rate)}/day</span>
            <span className="text-[12px] text-muted">{profile.experience_years}y experience</span>
          </div>

          <p className="text-[13px] leading-relaxed text-body">{profile.bio}</p>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-canvas px-3 py-2">
              <p className="eyebrow mb-1">Specialties</p>
              <p className="text-[12px] text-ink">
                {[profile.specialty, ...profile.secondary_specialties].map(titleCase).join(", ")}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-canvas px-3 py-2">
              <p className="eyebrow mb-1">Styles</p>
              <p className="text-[12px] text-ink">{profile.styles.map(titleCase).join(", ")}</p>
            </div>
            <div className="rounded-lg border border-line bg-canvas px-3 py-2 sm:col-span-2">
              <p className="eyebrow mb-1">Equipment</p>
              <p className="text-[12px] text-ink">{profile.equipment.join(" · ") || "Not listed"}</p>
            </div>
          </div>

          {profile.portfolio.length > 0 ? (
            <div>
              <p className="eyebrow mb-2">Portfolio ({profile.portfolio.length})</p>
              <div className="grid grid-cols-2 gap-2">
                {profile.portfolio.map((item) => (
                  <div key={item.id} className="overflow-hidden rounded-lg border border-line bg-canvas">
                    <img
                      src={item.url}
                      alt={item.title}
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      className="h-28 w-full object-cover"
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <p className="eyebrow mb-1.5">Unavailable dates</p>
            {profile.unavailable_dates.length ? (
              <div className="flex flex-wrap gap-1.5">
                {profile.unavailable_dates.map((date) => (
                  <span key={date} className="chip">
                    <CalendarX2 size={10} /> {formatDate(date)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[12px] text-muted">No blocked dates on record.</p>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
