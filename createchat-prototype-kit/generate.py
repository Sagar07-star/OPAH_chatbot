#!/usr/bin/env python3
"""Generate the CREATEchat prototype mock dataset into ./data.

Everything here is invented: names, companies, emails (example.com), phone
numbers (555), street addresses and portfolios. Nothing comes from OPAH's
database. The only real values are the public option codes in
data/project_options.json (the same lists the project form shows).

Dates are written relative to DATASET_TODAY so every status makes sense on
that day. Pass --today YYYY-MM-DD to shift the whole dataset.

    python generate.py                 # writes data/*.json
    python generate.py --today 2027-01-10
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATASET_TODAY = date(2026, 11, 16)
SEED = 20261116

CITIES = {
    # city: (lat, lng)
    "Miami, FL": (25.7617, -80.1918),
    "Miami Beach, FL": (25.7907, -80.1300),
    "Coral Gables, FL": (25.7215, -80.2684),
    "Fort Lauderdale, FL": (26.1224, -80.1373),
    "Hollywood, FL": (26.0112, -80.1495),
    "Boca Raton, FL": (26.3683, -80.1289),
    "West Palm Beach, FL": (26.7153, -80.0534),
}

FIRST = ["Ava", "Luis", "Priya", "Marcus", "Elena", "Theo", "Nia", "Diego", "Hana", "Caleb",
         "Zoe", "Rafael", "Imani", "Owen", "Leila", "Mateo", "Sofia", "Jonah", "Amara", "Felix",
         "Camila", "Isaac", "Rosa", "Dev"]
LAST = ["Reyes", "Okonjo", "Lindqvist", "Batista", "Moreau", "Kaplan", "Ferreira", "Novak",
        "Adeyemi", "Castillo", "Hwang", "Delgado", "Brennan", "Sato", "Mbeki", "Vargas",
        "Quinn", "Haddad", "Romero", "Ilić", "Navarro", "Osei", "Park", "Lowell"]

ROLE_PLAN = (["Photographer"] * 11) + (["Videographer"] * 9) + (["AI Artist"] * 4)
SPECIALTIES = {
    "Photographer": ["Commercial", "Product", "Portrait", "Fashion", "Real Estate", "Event", "Food", "Wedding"],
    "Videographer": ["Commercial", "Social Media", "Music Video", "Event", "Real Estate", "Corporate", "Documentary"],
    "AI Artist": ["AI Product Visualization", "AI Concept Art", "AI Video", "AI Brand Design"],
}
STYLES = ["bright and airy", "moody", "cinematic", "editorial", "minimal", "documentary",
          "high fashion", "warm film", "bold color", "clean commercial"]
EQUIPMENT = {
    "Photographer": ["Sony A7 IV", "Canon R5", "Nikon Z8", "Profoto B10 kit", "85mm f/1.4",
                     "24-70mm f/2.8", "DJI Mini 4 Pro (licensed)", "Backdrop kit"],
    "Videographer": ["Sony FX3", "Canon C70", "DJI RS 4 gimbal", "Aputure 300d kit",
                     "Rode wireless mics", "DJI Mavic 3 (licensed)", "Slider"],
    "AI Artist": ["Workstation (RTX 4090)", "Wacom Cintiq", "Licensed model suite"],
}


def d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def human(iso: str) -> str:
    """'2026-11-22' -> 'Sunday, Nov 22', for message text that must follow --today."""
    day = date.fromisoformat(iso)
    return f"{day:%A}, {day:%b} {day.day}"


def write(name: str, value) -> None:
    (DATA / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_talent(rng: random.Random) -> list[dict]:
    talent = []
    names = rng.sample([(f, l) for f in FIRST for l in LAST], len(ROLE_PLAN))
    cities = list(CITIES)
    for i, role in enumerate(ROLE_PLAN, start=1):
        first, last = names[i - 1]
        tid = f"tal_{i:03d}"
        specialty = SPECIALTIES[role][(i - 1) % len(SPECIALTIES[role])]
        secondary = rng.sample([s for s in SPECIALTIES[role] if s != specialty], 2)
        city = cities[(i * 3) % len(cities)]
        styles = rng.sample(STYLES, 3)
        rate = {"Photographer": rng.choice([450, 600, 750, 900, 1200, 1500]),
                "Videographer": rng.choice([650, 800, 1000, 1400, 1800, 2200]),
                "AI Artist": rng.choice([400, 550, 700, 950])}[role]
        years = rng.randint(2, 15)
        booked = sorted(d(o) for o in rng.sample(range(-5, 45), rng.randint(2, 6)))
        talent.append({
            "id": tid,
            "first_name": first,
            "last_name": last,
            "display_name": f"{first} {last[0]}.",
            "role": role,
            "specialty": specialty,
            "secondary_specialties": secondary,
            "city": city,
            "styles": styles,
            "day_rate": rate,
            "experience_years": years,
            "equipment": rng.sample(EQUIPMENT[role], min(3, len(EQUIPMENT[role]))),
            "bio": (f"{role} based in {city.split(',')[0]} with {years} years of "
                    f"{specialty.lower()} work. Known for a {styles[0]} look."),
            "rating": round(rng.uniform(4.3, 5.0), 1) if i % 5 else None,
            "completed_projects": rng.randint(0, 60),
            "portfolio": [
                {"id": f"{tid}_m{k}", "type": "video" if role == "Videographer" and k == 1 else "image",
                 "url": f"https://picsum.photos/seed/{tid}-{k}/1200/800",
                 "title": f"{specialty} work {k}"}
                for k in range(1, 5)
            ],
            "booked_dates": booked,
            "accepts_package_bookings": role != "AI Artist",
            "account_ready": i != 23,      # tal_023 has no payout account yet: add is blocked
            "portfolio_published": i != 24,  # tal_024 has not published a portfolio: add is blocked
        })
    return talent


def make_clients() -> list[dict]:
    return [
        {"id": "clt_001", "first_name": "Maya", "last_name": "Torres",
         "email": "maya.torres@coralbloom.example.com", "company": "Coral Bloom Skincare",
         "member_since": d(-420), "typical_budget": {"min": 1500, "max": 6000},
         "preferred_roles": ["Photographer", "Videographer"], "blocked_talent_ids": ["tal_018"],
         "notes": "Established brand client with a project in every status."},
        {"id": "clt_002", "first_name": "Jordan", "last_name": "Pike",
         "email": "jordan@pikeandco.example.com", "company": "Pike & Co Realty",
         "member_since": d(-160), "typical_budget": {"min": 300, "max": 1500},
         "preferred_roles": ["Photographer"], "blocked_talent_ids": [],
         "notes": "Real estate agent who books fixed-price packages."},
        {"id": "clt_003", "first_name": "Sam", "last_name": "Okafor",
         "email": "sam.okafor@example.com", "company": None,
         "member_since": d(-1), "typical_budget": None,
         "preferred_roles": [], "blocked_talent_ids": [],
         "notes": "Brand new client with no projects: the cold-start case."},
    ]


def make_packages() -> list[dict]:
    add_ons = {
        "drone": {"code": "DRONE", "label": "Drone aerials", "price": 150},
        "rush": {"code": "RUSH_48H", "label": "48-hour delivery", "price": 120},
        "extra_hour": {"code": "EXTRA_HOUR", "label": "Extra hour on site", "price": 175},
        "reels": {"code": "VERTICAL_CUTS", "label": "Three vertical social cuts", "price": 200},
    }
    return [
        {"id": "pkg_listing_starter", "category": "Photography", "title": "Listing Media Starter",
         "price": 349, "duration": "1.5 hours on site", "deliverables": ["25 edited photos"],
         "includes": ["Interior and exterior", "HDR editing", "Delivery in 48 hours"],
         "add_ons": [add_ons["drone"], add_ons["rush"]], "needs_location": True, "needs_call_time": True,
         "role": "Photographer", "specialty": "Real Estate"},
        {"id": "pkg_headshot_express", "category": "Photography", "title": "Headshot Express",
         "price": 249, "duration": "45 minutes", "deliverables": ["5 retouched headshots"],
         "includes": ["Two looks", "Studio or on location"], "add_ons": [add_ons["rush"]],
         "needs_location": True, "needs_call_time": True, "role": "Photographer", "specialty": "Portrait"},
        {"id": "pkg_product_pack", "category": "Photography", "title": "Product Photo Pack",
         "price": 449, "duration": "Half day", "deliverables": ["15 edited product photos"],
         "includes": ["White background and lifestyle", "Up to 8 products"], "add_ons": [add_ons["rush"]],
         "needs_location": True, "needs_call_time": True, "role": "Photographer", "specialty": "Product"},
        {"id": "pkg_event_reel", "category": "Video", "title": "Event Hype Reel",
         "price": 599, "duration": "2 hours on site", "deliverables": ["60-second highlight reel"],
         "includes": ["Licensed music", "One revision"], "add_ons": [add_ons["extra_hour"], add_ons["reels"]],
         "needs_location": True, "needs_call_time": True, "role": "Videographer", "specialty": "Event"},
        {"id": "pkg_business_promo", "category": "Video", "title": "Business Promo Reel",
         "price": 899, "duration": "3 hours on site", "deliverables": ["90-second promo", "Three 15-second cuts"],
         "includes": ["Interview audio", "Color grade"], "add_ons": [add_ons["drone"], add_ons["reels"]],
         "needs_location": True, "needs_call_time": True, "role": "Videographer", "specialty": "Commercial"},
        {"id": "pkg_social_day", "category": "Video", "title": "Social Content Day",
         "price": 1199, "duration": "6 hours on site", "deliverables": ["10 vertical videos", "30 photos"],
         "includes": ["Shot list planning call", "Two locations"], "add_ons": [add_ons["extra_hour"]],
         "needs_location": True, "needs_call_time": True, "role": "Videographer", "specialty": "Social Media"},
    ]


def _loc(line1, city, zip_code):
    c, st = city.split(", ")
    return {"line1": line1, "city": c, "state": st, "zip": zip_code, "country": "US",
            "display": f"{line1}, {c}, {st} {zip_code}"}


def make_projects(talent: list[dict]) -> tuple[list, list, list, list, list, list, list]:
    by_id = {t["id"]: t for t in talent}
    projects, bookings, folders, messages, documents, payments, proposals = [], [], [], [], [], [], []

    def project(pid, client, name, status, payment_status, source="custom", **fields):
        base = {
            "id": pid, "client_id": client, "name": name, "status": status,
            "payment_status": payment_status, "source": source,
            "project_type": None, "description": None, "start_date": None, "end_date": None,
            "scheduled_time": None, "duration_hours": None, "location": None,
            "role": None, "specialty": None, "budget": None, "budget_range": None,
            "deliverables": [], "lighting_styles": [], "point_of_contact": None,
            "priority": None, "client_notes": None, "deliverables_due_date": None,
            "package_id": None, "board_ids": [], "created_at": d(-30), "archived": False,
        }
        base.update(fields)
        projects.append(base)
        return base

    def booking(bid, pid, tid, status, rate, **extra):
        t = by_id[tid]
        row = {"id": bid, "project_id": pid, "talent_id": tid, "talent_name": t["display_name"],
               "role": t["role"], "status": status, "rate": rate, "counter_rate": None,
               "counter_message": None, "pending_change": None, "responded_at": None}
        row.update(extra)
        bookings.append(row)

    def pay(pid, client, amount, status, offset):
        fee = round(amount * 0.105)
        payments.append({"id": f"pay_{pid[4:]}", "project_id": pid, "client_id": client,
                         "subtotal": amount, "fee": fee, "total": amount + fee, "currency": "USD",
                         "status": status, "created_at": d(offset),
                         "receipt_url": f"https://receipts.example.com/{pid}"})

    # ---- clt_001: one project in each status ------------------------------
    project("prj_1001", "clt_001", "Holiday Gift Guide Shoot", "draft", "unpaid",
            role="Photographer", project_type="PRODUCT", created_at=d(-2))
    project("prj_1002", "clt_001", "Spring Lookbook", "draft", "unpaid",
            project_type="FASHION", role="Photographer", specialty="Fashion",
            description="Spring skincare lookbook: four models, outdoor garden setting, soft natural light.",
            start_date=d(18), end_date=d(18), scheduled_time="09:00", duration_hours=6,
            location=_loc("1420 Botanic Way", "Coral Gables, FL", "33134"), budget=2200,
            budget_range="1K_5K", deliverables=["EDITED_PHOTOS", "RETOUCHED_PHOTOS"],
            lighting_styles=["NATURAL", "SOFT"], point_of_contact="Maya Torres", priority="style")
    project("prj_1003", "clt_001", "Founder Portrait Series", "draft", "unpaid",
            project_type="PORTRAIT", role="Photographer", specialty="Portrait",
            description="Portraits of the three co-founders for press and the About page.",
            start_date=d(12), end_date=d(12), scheduled_time="14:00", duration_hours=3,
            location=_loc("88 Brickell Plaza, Suite 1200", "Miami, FL", "33131"), budget=900,
            budget_range="UNDER_1K", deliverables=["RETOUCHED_PHOTOS"], lighting_styles=["STUDIO"],
            point_of_contact="Maya Torres")
    booking("bkg_3001", "prj_1003", "tal_003", "countered", 900, counter_rate=1150,
            counter_message="Three setups in three hours needs an assistant; 1150 covers it.",
            responded_at=d(-1))
    project("prj_1004", "clt_001", "Product Launch Video", "escrow_held", "authorized",
            project_type="COMMERCIAL", role="Videographer", specialty="Commercial",
            description="45-second launch film for the new Dew Serum, plus vertical cuts.",
            start_date=d(5), end_date=d(5), scheduled_time="10:00", duration_hours=5,
            location=_loc("2300 Collins Ave", "Miami Beach, FL", "33139"), budget=3200,
            budget_range="1K_5K", deliverables=["EDITED_VIDEO", "SOCIAL_MEDIA_CUTS"],
            lighting_styles=["HIGH_KEY"], point_of_contact="Rina Patel (producer), 555-0142",
            deliverables_due_date=d(15))
    booking("bkg_4001", "prj_1004", "tal_014", "accepted", 3200, responded_at=d(-9))
    pay("prj_1004", "clt_001", 3200, "authorized", -9)
    documents.append({"id": "doc_4001", "project_id": "prj_1004", "type": "shot_list",
                      "title": "Shot list", "version": 2, "shared_with_talent": False,
                      "content_md": "| # | Scene | Shot type | Subject | Notes |\n| --- | --- | --- | --- | --- |\n"
                                    "| 1 | Bathroom counter | Macro | Serum drop | Slow motion |\n"
                                    "| 2 | Pool deck | Wide | Model applying | Golden hour |\n"
                                    "| 3 | Studio | Hero | Bottle on plinth | White sweep |"})
    project("prj_1005", "clt_001", "Pop-up Store Opening", "in_progress", "authorized",
            project_type="EVENT", role="Photographer", specialty="Event",
            description="Coverage of the Wynwood pop-up opening night.",
            start_date=d(0), end_date=d(0), scheduled_time="18:00", duration_hours=4,
            location=_loc("251 NW 26th St", "Miami, FL", "33127"), budget=1400,
            budget_range="1K_5K", deliverables=["EDITED_PHOTOS"], point_of_contact="Maya Torres")
    booking("bkg_5001", "prj_1005", "tal_006", "accepted", 1400, responded_at=d(-14))
    pay("prj_1005", "clt_001", 1400, "authorized", -14)
    project("prj_1006", "clt_001", "Summer Campaign Stills", "review", "authorized",
            project_type="COMMERCIAL", role="Photographer", specialty="Commercial",
            description="Campaign stills for the summer SPF line, beach and studio.",
            start_date=d(-10), end_date=d(-10), scheduled_time="07:30", duration_hours=8,
            location=_loc("1 Ocean Dr", "Miami Beach, FL", "33139"), budget=4800,
            budget_range="1K_5K", deliverables=["EDITED_PHOTOS", "RETOUCHED_PHOTOS"],
            point_of_contact="Maya Torres", deliverables_due_date=d(-1))
    booking("bkg_6001", "prj_1006", "tal_001", "accepted", 4800, responded_at=d(-30))
    pay("prj_1006", "clt_001", 4800, "authorized", -30)
    folders += [
        {"id": "fld_6001", "project_id": "prj_1006", "name": "Beach selects", "status": "submitted",
         "review_status": "pending_client", "submitted_at": d(-2), "review_due_at": d(5),
         "revision_note": None, "revisions_used": 0, "revisions_included": 2,
         "files": [{"id": f"fil_60{k:02d}", "name": f"beach_{k:02d}.jpg", "type": "image/jpeg",
                    "size_bytes": 8_400_000 + k * 1000,
                    "preview_url": f"https://picsum.photos/seed/fld6001-{k}/1200/800"} for k in range(1, 13)]},
        {"id": "fld_6002", "project_id": "prj_1006", "name": "Studio hero shots", "status": "submitted",
         "review_status": "pending_client", "submitted_at": d(-1), "review_due_at": d(6),
         "revision_note": "Warmer skin tones on 03 and 05, please.", "revisions_used": 1,
         "revisions_included": 2,
         "files": [{"id": f"fil_61{k:02d}", "name": f"studio_{k:02d}.jpg", "type": "image/jpeg",
                    "size_bytes": 9_100_000 + k * 1000,
                    "preview_url": f"https://picsum.photos/seed/fld6002-{k}/1200/800"} for k in range(1, 7)]},
    ]
    project("prj_1007", "clt_001", "Fall Catalog", "completed", "released",
            project_type="PRODUCT", role="Photographer", specialty="Product",
            description="Fall catalog product photography, 40 SKUs.",
            start_date=d(-60), end_date=d(-59), scheduled_time="09:00", duration_hours=8,
            location=_loc("500 Industrial Ln", "Hollywood, FL", "33020"), budget=3600,
            budget_range="1K_5K", deliverables=["EDITED_PHOTOS"], point_of_contact="Maya Torres")
    booking("bkg_7001", "prj_1007", "tal_002", "accepted", 3600, responded_at=d(-80))
    pay("prj_1007", "clt_001", 3600, "captured", -80)
    folders.append({"id": "fld_7001", "project_id": "prj_1007", "name": "Catalog finals",
                    "status": "submitted", "review_status": "approved", "submitted_at": d(-50),
                    "review_due_at": None, "revision_note": None, "revisions_used": 0,
                    "revisions_included": 2,
                    "files": [{"id": "fil_7001", "name": "fall_catalog_finals.zip", "type": "application/zip",
                               "size_bytes": 412_000_000, "preview_url": None}]})
    project("prj_1008", "clt_001", "Influencer Brunch", "cancelled", "refunded",
            project_type="EVENT", role="Videographer", specialty="Event",
            description="Brunch event coverage, cancelled when the venue fell through.",
            start_date=d(-20), end_date=d(-20), scheduled_time="11:00", duration_hours=3,
            location=_loc("1100 Biscayne Blvd", "Miami, FL", "33132"), budget=1100,
            point_of_contact="Maya Torres")
    pay("prj_1008", "clt_001", 1100, "refunded", -40)

    # ---- clt_002: package bookings ----------------------------------------
    project("prj_2001", "clt_002", "Listing Media Starter - 18 Palm Ave", "dispatching", "authorized",
            source="package", package_id="pkg_listing_starter", project_type="REAL_ESTATE",
            role="Photographer", specialty="Real Estate", start_date=d(2), end_date=d(2),
            scheduled_time="11:00", duration_hours=2, budget=349,
            location=_loc("18 Palm Ave", "Fort Lauderdale, FL", "33301"),
            description="3-bed condo listing, lockbox code shared on the day.", created_at=d(0))
    pay("prj_2001", "clt_002", 349, "authorized", 0)
    project("prj_2002", "clt_002", "Headshot Express - Team photo day", "assigned", "authorized",
            source="package", package_id="pkg_headshot_express", project_type="PORTRAIT",
            role="Photographer", specialty="Portrait", start_date=d(8), end_date=d(8),
            scheduled_time="09:30", duration_hours=1, budget=249,
            location=_loc("700 E Las Olas Blvd", "Fort Lauderdale, FL", "33301"))
    booking("bkg_2201", "prj_2002", "tal_011", "accepted", 249, responded_at=d(-3),
            pending_change={"kind": "date", "old": d(7), "new": d(8), "awaiting": "talent"})
    pay("prj_2002", "clt_002", 249, "authorized", -3)
    project("prj_2003", "clt_002", "Listing Media Starter - 4 Bayview Ct", "completed", "released",
            source="package", package_id="pkg_listing_starter", project_type="REAL_ESTATE",
            role="Photographer", specialty="Real Estate", start_date=d(-25), end_date=d(-25),
            scheduled_time="10:00", duration_hours=2, budget=349,
            location=_loc("4 Bayview Ct", "Boca Raton, FL", "33432"))
    booking("bkg_2301", "prj_2003", "tal_005", "accepted", 349, responded_at=d(-27))
    pay("prj_2003", "clt_002", 349, "captured", -27)
    folders.append({"id": "fld_2301", "project_id": "prj_2003", "name": "Listing photos",
                    "status": "submitted", "review_status": "approved", "submitted_at": d(-23),
                    "review_due_at": None, "revision_note": None, "revisions_used": 0,
                    "revisions_included": 1,
                    "files": [{"id": f"fil_23{k:02d}", "name": f"bayview_{k:02d}.jpg", "type": "image/jpeg",
                               "size_bytes": 6_000_000,
                               "preview_url": f"https://picsum.photos/seed/fld2301-{k}/1200/800"}
                              for k in range(1, 26)]})
    project("prj_2004", "clt_002", "Open House Walkthrough Video", "draft", "unpaid",
            project_type="REAL_ESTATE", role="Videographer", specialty="Real Estate",
            description="Two-minute walkthrough of a waterfront listing, with drone.",
            start_date=d(10), end_date=d(10), scheduled_time="15:00", duration_hours=3,
            location=_loc("31 Harbor Isle Dr", "Fort Lauderdale, FL", "33316"), budget=1250,
            budget_range="1K_5K", deliverables=["EDITED_VIDEO", "DRONE_FOOTAGE"],
            point_of_contact="Jordan Pike")
    booking("bkg_2401", "prj_2004", "tal_012", "accepted", 1250, responded_at=d(-1))

    # ---- messages ----------------------------------------------------------
    def msg(mid, pid, sender, sender_id, text, offset):
        messages.append({"id": mid, "project_id": pid, "sender": sender, "sender_id": sender_id,
                         "text": text, "sent_at": d(offset)})
    msg("msg_0001", "prj_1004", "talent", "tal_014",
        f"Hi Maya, could we move to {human(d(6))}? The pool deck is booked on {human(d(5))}.", -1)
    msg("msg_0002", "prj_1004", "client", "clt_001", "Let me check with the venue and get back to you today.", -1)
    msg("msg_0003", "prj_1005", "talent", "tal_006", "On my way, arriving 17:30 to scout the light.", 0)
    msg("msg_0004", "prj_1006", "talent", "tal_001", "Studio set is resubmitted with warmer tones on 03 and 05.", -1)
    msg("msg_0005", "prj_2002", "talent", "tal_011", "I'll bring a grey backdrop unless you prefer white.", -2)

    # ---- an open proposal the client never answered -------------------------
    proposals.append({"proposal_id": "prop_0001", "kind": "update_project", "client_id": "clt_001",
                      "project_id": "prj_1002", "summary": "Change 1 field on Spring Lookbook",
                      "changes": [{"field": "duration_hours", "label": "Duration (hours)", "old": 6, "new": 7}],
                      "status": "pending", "created_at": d(-1)})
    return projects, bookings, folders, messages, documents, payments, proposals


def make_boards() -> list[dict]:
    return [
        {"id": "brd_001", "client_id": "clt_001", "title": "Dewy summer skin", "project_ids": ["prj_1006"],
         "items": [{"id": f"brd_001_i{k}", "type": "image",
                    "url": f"https://picsum.photos/seed/brd001-{k}/900/1200", "note": None} for k in range(1, 9)]},
        {"id": "brd_002", "client_id": "clt_001", "title": "Launch film references", "project_ids": ["prj_1004"],
         "items": [{"id": "brd_002_i1", "type": "video", "url": "https://videos.example.com/ref-1",
                    "note": "Love the slow macro drip"},
                   {"id": "brd_002_i2", "type": "image",
                    "url": "https://picsum.photos/seed/brd002-2/1200/800", "note": None}]},
    ]


def make_support() -> list[dict]:
    return [{"id": "tkt_0001", "client_id": "clt_001", "subject": "Receipt shows the wrong company name",
             "category": "billing", "status": "waiting_on_team", "status_label": "With our team",
             "created_at": d(-3), "updated_at": d(-2)}]


def main() -> None:
    global TODAY
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", default=DATASET_TODAY.isoformat())
    args = parser.parse_args()
    TODAY = date.fromisoformat(args.today)
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)

    talent = make_talent(rng)
    projects, bookings, folders, messages, documents, payments, proposals = make_projects(talent)
    write("meta.json", {"dataset_today": TODAY.isoformat(), "seed": SEED, "currency": "USD",
                        "assistance_fee_rate": 0.105, "timezone": "America/New_York",
                        "cities": {k: {"lat": v[0], "lng": v[1]} for k, v in CITIES.items()},
                        "note": "Synthetic data. No real people, companies, addresses or accounts."})
    write("clients.json", make_clients())
    write("talent.json", talent)
    write("packages.json", make_packages())
    write("projects.json", projects)
    write("bookings.json", bookings)
    write("deliverables.json", folders)
    write("messages.json", messages)
    write("documents.json", documents)
    write("payments.json", payments)
    write("proposals.json", proposals)
    write("boards.json", make_boards())
    write("support_tickets.json", make_support())
    print(f"Wrote mock dataset for {TODAY.isoformat()} to {DATA}")


TODAY = DATASET_TODAY

if __name__ == "__main__":
    main()
