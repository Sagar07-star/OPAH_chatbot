"""Checks the mock kit implements the contract and its rules.

Each test walks one workflow from the brief's Target workflows table, so they
double as examples of the tool calls a conversation should make.

    python -m unittest test_mock_tools.py
"""
import unittest

from mock_tools import TOOLS, MockOPAH, tool_schemas

MAYA, JORDAN, SAM = "clt_001", "clt_002", "clt_003"


class MockKitTest(unittest.TestCase):
    def setUp(self):
        self.api = MockOPAH()

    def call(self, tool, user=MAYA, **args):
        return self.api.call(tool, args, user=user)

    # ---- access and isolation -------------------------------------------
    def test_anonymous_visitors_get_only_public_tools(self):
        self.assertIn("talents", self.call("search_talent", user=None, role="videographer"))
        self.assertIn("packages", self.call("list_packages", user=None))
        for tool in ("get_account_summary", "list_projects", "update_project"):
            self.assertEqual(self.call(tool, user=None).get("error"), "auth_required", tool)

    def test_one_client_never_sees_anothers_project(self):
        res = self.call("get_project", user=JORDAN, project_id="prj_1002")
        self.assertEqual(res["error"], "not_found")
        res = self.call("update_project", user=JORDAN, project_id="prj_1002", changes={"budget": 1})
        self.assertEqual(res["error"], "not_found")

    def test_a_client_cannot_approve_someone_elses_proposal(self):
        prop = self.call("update_project", project_id="prj_1002", changes={"budget": 2500})
        self.assertEqual(self.api.approve_proposal(prop["proposal_id"], JORDAN)["error"], "not_found")

    def test_blocked_creatives_never_appear(self):
        found = self.call("search_talent", role="videographer", limit=10)["talent_ids"]
        self.assertNotIn("tal_018", found)
        self.assertEqual(self.call("get_talent_profile", talent_id="tal_018")["error"], "not_found")

    def test_profiles_hide_internal_flags(self):
        profile = self.call("get_talent_profile", talent_id="tal_001")
        for hidden in ("account_ready", "portfolio_published", "booked_dates"):
            self.assertNotIn(hidden, profile)

    # ---- workflow 1: start a project -----------------------------------
    def test_create_project_applies_only_on_approval(self):
        before = len(self.call("list_projects", user=SAM)["projects"])
        prop = self.call("create_project", user=SAM, fields={
            "name": "Cafe menu shoot", "role": "photog", "project_type": "FOOD_BEVERAGE", "budget": "$900"})
        self.assertEqual(prop["status"], "pending")
        self.assertEqual(len(self.call("list_projects", user=SAM)["projects"]), before)
        applied = self.api.approve_proposal(prop["proposal_id"], SAM)
        project = self.call("get_project", user=SAM, project_id=applied["result"]["project_id"])
        self.assertEqual((project["role"], project["budget"]), ("Photographer", 900))

    def test_invented_option_codes_are_refused(self):
        res = self.call("create_project", user=SAM, fields={"name": "X", "project_type": "LIFESTYLE"})
        self.assertEqual(res["error"], "invalid_fields")

    # ---- workflow 2: fill missing details ------------------------------
    def test_update_stages_a_diff_and_double_approval_is_refused(self):
        prop = self.call("update_project", project_id="prj_1002",
                         changes={"start_date": "2026-12-11", "end_date": "2026-12-11", "budget": 2500})
        self.assertEqual({c["field"] for c in prop["changes"]}, {"start_date", "end_date", "budget"})
        self.assertEqual(self.api.approve_proposal(prop["proposal_id"], MAYA)["status"], "applied")
        self.assertEqual(self.api.approve_proposal(prop["proposal_id"], MAYA)["error"], "already_applied")
        self.assertEqual(self.call("get_project", project_id="prj_1002")["budget"], 2500)

    def test_paid_projects_lock_most_fields(self):
        res = self.call("update_project", project_id="prj_1004", changes={"role": "Photographer"})
        self.assertEqual(res["error"], "field_locked")
        res = self.call("update_project", project_id="prj_1007", changes={"name": "New"})
        self.assertEqual(res["error"], "non_editable")

    def test_same_values_are_no_change(self):
        res = self.call("update_project", project_id="prj_1002", changes={"budget": 2200})
        self.assertEqual(res["error"], "no_changes")

    # ---- workflows 4-5: find and book ----------------------------------
    def test_search_relaxes_and_says_so(self):
        res = self.call("search_talent", role="videographer", location="Boca Raton", budget_max=500)
        self.assertTrue(res["relaxed"])

    def test_adding_talent_checks_the_rules(self):
        blocked = self.call("add_talent_to_project", project_id="prj_1001", talent_id="tal_001")
        self.assertEqual(blocked["error"], "rule_blocked")          # draft is missing fields
        self.assertIn("missing_fields", blocked)
        wrong_role = self.call("add_talent_to_project", project_id="prj_1002", talent_id="tal_014")
        self.assertEqual(wrong_role["error"], "rule_blocked")
        # The one fashion specialist is booked on the Spring Lookbook date.
        busy = self.call("add_talent_to_project", project_id="prj_1002", talent_id="tal_004")
        self.assertEqual(busy["conflict_dates"], ["2026-12-04"])
        found = self.call("search_talent", role="photographer", specialty="Fashion", date="2026-12-04")
        self.assertNotIn("tal_004", found["talent_ids"])
        prop = self.call("add_talent_to_project", project_id="prj_1002", talent_id="tal_001")
        self.assertEqual(self.api.approve_proposal(prop["proposal_id"], MAYA)["status"], "applied")
        statuses = {b["talent_id"]: b["status"] for b in self.call("get_project", project_id="prj_1002")["bookings"]}
        self.assertEqual(statuses["tal_001"], "added")

    def test_a_project_books_one_creative(self):
        res = self.call("add_talent_to_project", user=JORDAN, project_id="prj_2004", talent_id="tal_019")
        self.assertEqual(res["error"], "rule_blocked")

    # ---- workflow 6: counter-offers -------------------------------------
    def test_accepting_a_counter_offer_sets_the_rate(self):
        prop = self.call("respond_to_counter_offer", project_id="prj_1003", booking_id="bkg_3001", decision="accept")
        self.api.approve_proposal(prop["proposal_id"], MAYA)
        booking = self.call("get_project", project_id="prj_1003")["bookings"][0]
        self.assertEqual((booking["status"], booking["rate"]), ("accepted", 1150))

    # ---- workflow 7: pay --------------------------------------------------
    def test_checkout_is_a_handoff_with_the_fee(self):
        res = self.call("prepare_checkout", user=JORDAN, project_ids=["prj_2004"])
        summary = res["handoff"]["summary"]
        self.assertEqual((summary["subtotal"], summary["fee"], summary["total"]), (1250, 131, 1381))
        self.assertEqual(self.call("get_project", user=JORDAN, project_id="prj_2004")["payment_status"], "unpaid")

    def test_checkout_explains_what_is_not_ready(self):
        res = self.call("prepare_checkout", project_ids=["prj_1002"])
        self.assertEqual(res["error"], "rule_blocked")
        self.assertIn("no creative has accepted yet", res["not_ready"][0]["issues"])

    def test_package_booking_checks_notice_area_and_add_ons(self):
        ok = self.call("prepare_package_booking", user=JORDAN, package_id="pkg_listing_starter",
                       address="9 Coral Way, Miami, FL", date="2026-11-20", call_time="10:00", add_ons=["DRONE"])
        self.assertEqual(ok["handoff"]["summary"]["subtotal"], 499)
        soon = self.call("prepare_package_booking", user=JORDAN, package_id="pkg_listing_starter",
                         address="9 Coral Way, Miami, FL", date="2026-11-16", call_time="18:00")
        self.assertEqual(soon["error"], "rule_blocked")
        far = self.call("prepare_package_booking", user=JORDAN, package_id="pkg_listing_starter",
                        address="1 Main St, Orlando, FL", date="2026-11-20", call_time="10:00")
        self.assertEqual(far["error"], "rule_blocked")

    # ---- workflows 8, 9, 15: plan, talk, inspire ----------------------
    def test_sharing_a_document_and_drafting_a_message(self):
        prop = self.call("share_document", project_id="prj_1004", document_id="doc_4001")
        self.api.approve_proposal(prop["proposal_id"], MAYA)
        self.assertTrue(self.call("get_project", project_id="prj_1004")["documents"][0]["shared_with_talent"])
        draft = self.call("draft_message", project_id="prj_1004", text="The 6th works, see you then.")
        self.assertEqual(draft["handoff"]["screen"], "project_messages")

    def test_boards(self):
        prop = self.call("create_board", title="Gift guide refs", project_id="prj_1001", items=["https://a/1.jpg"])
        board_id = self.api.approve_proposal(prop["proposal_id"], MAYA)["result"]["board_id"]
        self.assertIn(board_id, [b["id"] for b in self.call("list_boards")["boards"]])

    # ---- workflows 10-11: reschedule and cancel -----------------------
    def test_rescheduling_a_paid_project_waits_for_the_creative(self):
        prop = self.call("update_project", project_id="prj_1004",
                         changes={"start_date": "2026-11-22", "end_date": "2026-11-22"})
        result = self.api.approve_proposal(prop["proposal_id"], MAYA)["result"]
        self.assertIn("must accept", result["note"])

    def test_cancellation_tiers(self):
        self.assertEqual(self.call("get_cancellation_preview", project_id="prj_1004")["refund_percent"], 75)
        self.assertEqual(self.call("get_cancellation_preview", user=JORDAN, project_id="prj_2001")["tier"],
                         "no_creative_yet")
        self.assertEqual(self.call("get_cancellation_preview", project_id="prj_1005")["error"], "rule_blocked")
        self.assertEqual(self.call("prepare_cancellation", project_id="prj_1004")["handoff"]["screen"],
                         "cancel_project")

    # ---- workflows 13-14: deliverables and reviews --------------------
    def test_approving_every_folder_completes_the_project(self):
        for folder in ("fld_6001", "fld_6002"):
            prop = self.call("review_deliverable", project_id="prj_1006", folder_id=folder, decision="approve")
            self.api.approve_proposal(prop["proposal_id"], MAYA)
        self.assertEqual(self.call("get_project", project_id="prj_1006")["status"], "completed")
        self.assertIn("handoff", self.call("draft_review", project_id="prj_1006", rating=5, text="Great."))

    def test_revision_needs_a_note_and_counts_rounds(self):
        self.assertEqual(self.call("review_deliverable", project_id="prj_1006", folder_id="fld_6001",
                                   decision="request_revision")["error"], "invalid_fields")
        prop = self.call("review_deliverable", project_id="prj_1006", folder_id="fld_6001",
                         decision="request_revision", note="Less contrast on 04.")
        self.assertEqual(self.api.approve_proposal(prop["proposal_id"], MAYA)["result"]["review_status"],
                         "revision_requested")

    # ---- workflow 17: briefing ------------------------------------------
    def test_account_summary_flags_everything(self):
        kinds = {i["kind"] for i in self.call("get_account_summary")["needs_attention"]}
        self.assertTrue({"counter_offer", "deliverables_to_review", "draft_incomplete",
                         "proposal_pending"} <= kinds)
        jordan = {i["kind"] for i in self.call("get_account_summary", user=JORDAN)["needs_attention"]}
        self.assertTrue({"change_awaiting_talent", "finding_creative", "ready_to_pay"} <= jordan)
        self.assertEqual(self.call("get_account_summary", user=SAM)["needs_attention"], [])

    def test_rejected_proposals_stay_rejected(self):
        self.assertEqual(self.api.reject_proposal("prop_0001", MAYA)["status"], "rejected")
        self.assertEqual(self.api.approve_proposal("prop_0001", MAYA)["error"], "already_rejected")

    def test_every_tool_has_a_schema(self):
        self.assertEqual({s["name"] for s in tool_schemas()}, set(TOOLS))


if __name__ == "__main__":
    unittest.main()
