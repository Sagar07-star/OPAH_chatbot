export type Role = "client" | "talent" | "anonymous";

export type ProjectStatus =
  | "draft"
  | "dispatching"
  | "escrow_held"
  | "assigned"
  | "initiated"
  | "in_progress"
  | "captured"
  | "review"
  | "completed"
  | "cancelled";

export interface DemoAccount {
  id: string;
  name: string;
  first_name: string;
  company: string | null;
  email: string;
  member_since: string;
  kind: string;
}

export interface SessionInfo {
  user_id: string;
  role: Role;
  authenticated: boolean;
  display_name: string;
  company: string | null;
  initials: string;
  member_since: string | null;
}

export interface Conversation {
  id: string;
  client_id: string;
  project_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
  project_name?: string | null;
  project_status?: string | null;
}

export interface SessionMeta {
  session: SessionInfo;
  accounts: DemoAccount[];
  dataset_today: string;
  assistance_fee_rate: number;
  model: { configured: boolean; name: string; env: string };
  active_project_id: string | null;
  conversations: Conversation[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  status: ProjectStatus;
  payment_status: string;
  source: string;
  start_date: string | null;
  end_date: string | null;
  scheduled_time: string | null;
  duration_hours: number | null;
  role: string | null;
  specialty: string | null;
  budget: number | null;
  location: string | null;
  talent: string | null;
  deliverables: string[];
}

export interface Booking {
  id: string;
  project_id: string;
  talent_id: string;
  talent_name: string;
  role: string;
  status: string;
  rate: number;
  counter_rate: number | null;
  counter_message: string | null;
  pending_change: { kind: string; old: string | number; new: string | number; awaiting: string } | null;
  responded_at: string | null;
}

export interface DeliverableFile {
  id: string;
  name: string;
  type: string;
  size_bytes: number;
  preview_url: string | null;
}

export interface DeliverableFolder {
  id: string;
  project_id: string;
  name: string;
  status: string;
  review_status: string;
  submitted_at: string;
  review_due_at: string | null;
  revision_note: string | null;
  revisions_used: number;
  revisions_included: number;
  files?: DeliverableFile[];
  file_count?: number;
  project_name?: string;
}

export interface ProjectDocument {
  id: string;
  project_id: string;
  type: string;
  title: string;
  version: number;
  shared_with_talent: boolean;
  content_md?: string;
  created_at?: string;
  project_name?: string | null;
  project_status?: string | null;
}

export interface ProjectDetail extends ProjectSummary {
  description: string | null;
  point_of_contact: string | null;
  priority: string | null;
  client_notes: string | null;
  deliverables_due_date: string | null;
  project_type: string;
  budget_range: string | null;
  lighting_styles: string[];
  package_id: string | null;
  bookings: Booking[];
  deliverable_folders: DeliverableFolder[];
  documents: ProjectDocument[];
  open_proposals: Proposal[];
  missing_fields: string[];
  editable_fields: string[];
  display_location: string | null;
  field_labels: Record<string, string>;
  payment: { subtotal: number; fee: number; total: number; status: string; currency: string } | null;
}

export interface AttentionItem {
  kind: string;
  project_id?: string;
  project?: string;
  detail: string;
  talent?: string;
  booking_id?: string;
  folder_id?: string;
  proposal_id?: string;
}

export interface UpcomingShoot {
  id: string;
  name: string;
  status: ProjectStatus;
  start_date: string;
  role: string | null;
  budget: number | null;
  talent: string | null;
  location: string | null;
  scheduled_time: string | null;
  duration_hours: number | null;
  specialty?: string | null;
}

export interface AccountSummary {
  client: { id: string; first_name: string; company: string | null };
  today: string;
  upcoming_shoots: UpcomingShoot[];
  needs_attention: AttentionItem[];
  project_counts: Partial<Record<ProjectStatus, number>>;
  open_support_tickets: number;
  projects: ProjectSummary[];
  open_proposals: Proposal[];
  totals: { projects: number; boards: number; documents: number; pending_proposals: number };
}

export interface MatchInfo {
  score: number;
  reasons: string[];
}

export interface Talent {
  id: string;
  name: string;
  role: string;
  specialty: string;
  city: string;
  day_rate: number;
  rating: number;
  experience_years: number;
  styles: string[];
  distance_miles: number | null;
  thumbnail: string;
  match: MatchInfo;
}

export interface TalentProfile {
  id: string;
  name: string;
  role: string;
  specialty: string;
  secondary_specialties: string[];
  city: string;
  styles: string[];
  day_rate: number;
  experience_years: number;
  equipment: string[];
  bio: string;
  rating: number;
  completed_projects: number;
  portfolio: { id: string; type: string; url: string; title: string }[];
  unavailable_dates: string[];
  accepts_package_bookings: boolean;
}

export interface PackageAddOn {
  code: string;
  label: string;
  price: number;
}

export interface Package {
  id: string;
  category: string;
  title: string;
  price: number;
  duration: string;
  deliverables: string[];
  includes: string[];
  add_ons: PackageAddOn[];
  role: string;
  specialty: string;
}

export interface ProposalChange {
  field: string;
  label: string;
  old: unknown;
  new: unknown;
}

export interface Proposal {
  proposal_id: string;
  kind: string;
  project_id: string | null;
  project_name: string | null;
  summary: string;
  changes: ProposalChange[];
  status: "pending" | "applied" | "rejected" | "applying" | string;
  created_at: string | null;
  applies?: string;
  result?: Record<string, unknown> | null;
}

export interface HandoffSummary {
  [key: string]: unknown;
}

export interface Handoff {
  screen: string;
  title: string;
  params: Record<string, unknown>;
  summary: HandoffSummary;
  disclaimer: string;
}

export interface PlanningDoc {
  type: string;
  title: string;
  content_md: string;
}

export interface Board {
  id: string;
  title: string;
  project_ids: string[];
  project_names: string[];
  items: { id: string; type: string; url: string; note: string | null }[];
}

export interface SupportTicket {
  id: string;
  subject: string;
  category: string;
  status: string;
  status_label?: string | null;
  created_at: string;
  source?: string;
}

export interface CancellationPreview {
  project_id: string;
  tier: string;
  refund_percent: number | null;
  refund_amount: number;
  paid_total?: number;
  hours_until_start?: number;
  message?: string;
}

export interface Card {
  type: string;
  proposal?: Proposal;
  handoff?: Handoff;
  planning?: PlanningDoc;
  project_id?: string | null;
  project_name?: string | null;
  can_save?: boolean;
  save_hint?: string;
  summary?: AccountSummary;
  project?: ProjectDetail;
  projects?: ProjectSummary[];
  count?: number;
  talents?: Talent[];
  talent?: TalentProfile;
  folders?: DeliverableFolder[];
  messages?: { id: string; sender: string; text: string; sent_at: string }[];
  packages?: Package[];
  service_area?: string[];
  assistance_fee_rate?: number;
  boards?: Board[];
  tickets?: SupportTicket[];
  note?: string;
  stub?: boolean;
  title?: string;
  message?: string;
  connected?: boolean;
  diagnosis?: {
    topic: string;
    facts: string[];
    fixes: string[];
    help_steps: string[];
    stub: boolean;
  };
  preview?: CancellationPreview;
  catalogs?: Record<string, { label: string; multi: boolean; options: { value: string; label: string }[] }>;
  applied?: Record<string, unknown>;
  relaxed?: string[];
  role_notice?: string | null;
  ticket?: SupportTicket;
}

export interface Envelope {
  type:
    | "text"
    | "talent_results"
    | "action_proposal"
    | "handoff"
    | "account_summary"
    | "project_details"
    | "project_list"
    | "talent_profile"
    | "planning_card"
    | "pulse"
    | "error";
  message: string;
  data: {
    cards?: Card[];
    tools_used?: string[];
    proposals?: Proposal[];
    handoff?: Handoff;
    planning?: PlanningDoc;
    talents?: Talent[];
    summary?: AccountSummary;
    error_code?: string;
    reference?: string;
    setup_required?: boolean;
    model_env?: string;
    [key: string]: unknown;
  };
  actions: { label: string; prompt: string }[];
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  envelope: Envelope | null;
  created_at: string;
  pending?: boolean;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  user_message_id: string;
  envelope: Envelope;
  persona: { name: string; label: string; detour: string | null; reason: string };
  tool_calls: { name: string; ok: boolean; error: string | null; arguments: Record<string, unknown> }[];
  model: string;
  created_at: string;
  conversation: Conversation | null;
}

export interface UploadRecord {
  id: string;
  filename: string;
  mime: string;
  size_bytes: number;
  pages: number | null;
  has_text: boolean;
}

export interface ProposalResponse {
  proposal_id: string;
  status: string;
  applied?: boolean;
  rejected?: boolean;
  already?: boolean;
  error?: string | null;
  message?: string | null;
  result?: Record<string, unknown> | null;
  proposal: Proposal;
}
