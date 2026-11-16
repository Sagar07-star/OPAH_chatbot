# CREATEchat prototype kit

Synthetic data and a working mock of the tool layer for building the CREATEchat
assistant prototype without access to OPAH's systems. Read the contractor brief
first; this kit implements its "Prototype contract" section.

Everything in `data/` is invented: people, companies, emails (`example.com`),
phone numbers (555), addresses and portfolios. The only real values are the
public option codes in `data/project_options.json`.

Python 3.10+ and the standard library only. Nothing to install.

## Contents

| File | What it is |
| --- | --- |
| `data/*.json` | The dataset: clients, creatives, packages, projects, bookings, deliverables, messages, documents, payments, proposals, boards, support tickets |
| `mock_tools.py` | Every read, staging and hand-off tool, plus proposal approval, with the business rules |
| `server.py` | The same tools over HTTP, for a prototype in any language |
| `tool_schemas.json` | Tool definitions in function-calling format, ready to hand to a model |
| `scenarios.json` | 27 starter test conversations with expected tool calls |
| `test_mock_tools.py` | Tests that walk every target workflow (also worked examples) |
| `generate.py` | Rebuilds `data/` deterministically; `--today` shifts every date |

## Quick start

```bash
python3 server.py
```

```bash
curl -s -X POST localhost:8765/tools/get_account_summary -H 'X-Mock-User: clt_001'
```

```bash
curl -s -X POST localhost:8765/tools/update_project -H 'X-Mock-User: clt_001' \
  -d '{"project_id": "prj_1002", "changes": {"budget": 2500}}'
```

```bash
curl -s -X POST localhost:8765/proposals/prop_1001/approve -H 'X-Mock-User: clt_001'
```

`POST /reset` reloads the dataset. `GET /state` shows every record as it stands.

From Python, skip the server:

```python
from mock_tools import MockOPAH
api = MockOPAH()
api.call("search_talent", {"role": "photog", "location": "brickell"}, user="clt_001")
```

## Identity

The signed-in client comes from the `X-Mock-User` header (or the `user`
argument), never from tool arguments. Leave it out to act as an anonymous
visitor, who may only call `search_talent`, `get_project_options` and
`list_packages`.

## Test clients

| Id | Who | Use it to test |
| --- | --- | --- |
| `clt_001` | Maya Torres, Coral Bloom Skincare | Every project status, counter-offers, deliverable review, rescheduling a paid shoot, briefing |
| `clt_002` | Jordan Pike, Pike & Co Realty | Fixed-price packages, checkout hand-off |
| `clt_003` | Sam Okafor, new client | Cold start: no projects |

## The dataset day

All dates are relative to **2026-11-16**, noon, Miami time, so every status is
consistent on that day. The mock clock stays there. To move the whole dataset:

```bash
python3 generate.py --today 2027-02-01
```

## Projects and what each one exercises

| Project | Client | Status | Exercises |
| --- | --- | --- | --- |
| `prj_1001` Holiday Gift Guide Shoot | Maya | draft, most fields empty | Project builder asking for missing details; adding a creative is blocked |
| `prj_1002` Spring Lookbook | Maya | draft, complete, no creative | Talent search; the best fashion fit (`tal_004`) is busy that day; an old unanswered proposal (`prop_0001`) |
| `prj_1003` Founder Portrait Series | Maya | draft, counter-offer open | Accepting or denying a counter-offer ($900 to $1,150) |
| `prj_1004` Product Launch Video | Maya | paid, shoot in 5 days | Locked fields; the creative asked by message to move a day later, so rescheduling then waits for their acceptance; sharing the shot list; drafting a reply; cancellation preview (75% tier) |
| `prj_1005` Pop-up Store Opening | Maya | in progress today | Cancellation goes to review; shoot-day questions |
| `prj_1006` Summer Campaign Stills | Maya | in review, two folders waiting | Approving deliverables, requesting a revision; approving both completes the project |
| `prj_1007` Fall Catalog | Maya | completed | Read-only history; drafting a review |
| `prj_1008` Influencer Brunch | Maya | cancelled | Not editable |
| `prj_2001` Listing Media Starter, 18 Palm Ave | Jordan | package paid, finding a creative | Status while offered to creatives; full refund (no creative yet) |
| `prj_2002` Headshot Express | Jordan | package, creative assigned | A date change waiting for the creative |
| `prj_2003` Listing Media Starter, 4 Bayview Ct | Jordan | completed | History |
| `prj_2004` Open House Walkthrough Video | Jordan | draft, creative accepted, unpaid | Checkout hand-off ($1,250 + $131 fee = $1,381) |

## Creatives with a catch

| Id | Catch |
| --- | --- |
| `tal_004` | The only fashion photographer; booked on the Spring Lookbook date |
| `tal_018` | Blocked by Maya: must never appear to her in search or profiles |
| `tal_023` | No payout account yet: can't be added to a project |
| `tal_024` | Portfolio not published: can't be added to a project |

## Rules the mock enforces

- A client only ever sees and changes their own records. Someone else's id
  returns `not_found`, exactly like a missing one.
- Staging tools change nothing. Approval applies the change once; a second
  approval returns `already_applied`, a declined one `already_rejected`.
- Paid projects only allow schedule, location, description, contact, notes,
  name and budget changes. Completed and cancelled projects allow none.
- A date or budget change on a paid project with a creative waits for the
  creative to accept it.
- Adding a creative needs a complete draft, the matching role, a bookable
  creative who is free on every project date, no block between the two, and
  no creative already accepted (a project books one).
- Option codes must come from `get_project_options`.
- Checkout and package booking are hand-offs: they price the booking (10.5%
  assistance fee added) and never charge. Packages need 24 hours' notice and a
  South Florida address.
- Cancellation preview follows the policy: more than 7 days, 100%; 7 days to
  3 hours, 75%; 3 to 1 hour, 0%; inside an hour or after the start, review.

## Scenarios

Each entry in `scenarios.json` gives the viewer, active project, persona,
project state, intent, an optional hard case, the client's turns, and what is
expected: tools that must and must not be called, the reply `type`, and words
the reply must or must not contain. Match words case-insensitively, ignoring
`$`, commas and hyphens. `approve_proposal` in `must_not_call` means no write
may happen in that conversation. Run each scenario after `POST /reset`.

## Not in the kit

Support tools (diagnose, tickets, notifications), uploads and vision, content
moderation and rate limits. The brief describes how production handles them;
stub them in the prototype.
