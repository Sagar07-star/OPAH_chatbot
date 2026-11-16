import type { Card } from "../../types";
import { HandoffCard } from "./HandoffCard";
import { PlanningCard } from "./PlanningCard";
import { ProposalCard } from "./ProposalCard";
import { TalentResultCards } from "./TalentCards";
import {
  AccountSummaryPanel,
  BoardsPanel,
  CancellationPanel,
  DeliverablesPanel,
  DiagnosisPanel,
  MessagesPanel,
  OptionsPanel,
  PackagesPanel,
  ProjectDetailsPanel,
  ProjectListPanel,
  StubNoticePanel,
  SupportTicketsPanel,
  TicketCreatedPanel,
} from "./OtherCards";

export interface CardContext {
  isClient: boolean;
  projectId: string | null;
  projectName: string | null;
  onProposalUpdated: (proposalId: string, status: string) => void;
  onOpenProfile: (talentId: string) => void;
  onPrompt: (text: string) => void;
}

export function CardRenderer({ card, context }: { card: Card; context: CardContext }) {
  switch (card.type) {
    case "action_proposal":
      return card.proposal ? (
        <ProposalCard proposal={card.proposal} onUpdated={context.onProposalUpdated} />
      ) : null;
    case "handoff":
      return card.handoff ? <HandoffCard handoff={card.handoff} /> : null;
    case "planning_card":
      return card.planning ? (
        <PlanningCard
          planning={card.planning}
          projectId={card.project_id ?? context.projectId}
          projectName={card.project_name ?? context.projectName}
          canSave={Boolean(card.can_save)}
          saveHint={card.save_hint}
        />
      ) : null;
    case "talent_results":
      return (
        <TalentResultCards
          talents={card.talents ?? []}
          count={card.count}
          relaxed={card.relaxed}
          roleNotice={card.role_notice}
          isClient={context.isClient}
          projectName={context.projectName}
          onPrompt={context.onPrompt}
          onOpenProfile={context.onOpenProfile}
        />
      );
    case "account_summary":
      return card.summary ? <AccountSummaryPanel summary={card.summary} /> : null;
    case "project_details":
      return card.project ? <ProjectDetailsPanel project={card.project} /> : null;
    case "project_list":
      return <ProjectListPanel projects={card.projects ?? []} />;
    case "deliverables":
      return <DeliverablesPanel folders={card.folders ?? []} />;
    case "messages":
      return <MessagesPanel messages={card.messages ?? []} />;
    case "packages":
      return (
        <PackagesPanel
          packages={card.packages ?? []}
          onPrompt={context.onPrompt}
          isClient={context.isClient}
        />
      );
    case "boards":
      return <BoardsPanel boards={card.boards ?? []} />;
    case "diagnosis":
      return card.diagnosis ? <DiagnosisPanel diagnosis={card.diagnosis} /> : null;
    case "support_tickets":
      return <SupportTicketsPanel tickets={card.tickets ?? []} note={card.note} />;
    case "support_ticket_created":
      return <TicketCreatedPanel ticket={card.ticket} note={card.note} />;
    case "stub_notice":
      return <StubNoticePanel title={card.title} message={card.message} />;
    case "cancellation_preview":
      return card.preview ? <CancellationPanel preview={card.preview} /> : null;
    case "project_options":
      return card.catalogs ? <OptionsPanel catalogs={card.catalogs} /> : null;
    default:
      return null;
  }
}
