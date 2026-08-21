import unittest
from unittest.mock import patch

from career_copilot.analyzer import analyze, extract_salary
from career_copilot.profile import build_profile
from career_copilot.tailor import tailor
from career_copilot.validator import validate_fact_ids
from career_copilot.validator import validate_claims
from career_copilot.pdf_export import render_pdf
from career_copilot.ai import AIConfig, AIError, assess_fit, plan_materials, status


RESUME = """Jordan Example
Principal Infrastructure Architect
2018-Present — Led enterprise storage architecture using NetApp, Pure, VMware, and S3.
Designed Zero Trust controls aligned with NIST for regulated environments.
Mentored engineering teams and presented technology strategy to executives.
Delivered major platform migrations with no unplanned customer downtime.
"""
JOB = """We seek a Principal Infrastructure Architect to lead enterprise storage and security architecture.
The successful candidate will use NetApp, VMware, S3, NIST, and Zero Trust practices, mentor engineers,
and present strategy to leadership. This remote role pays $160,000 - $195,000 and requires 10% travel.
Azure experience is preferred. Candidates collaborate across security and infrastructure teams.
"""


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.profile = build_profile({"name": "Jordan Example", "headline": "Principal Infrastructure Architect", "master_resume": RESUME, "preferences": {"target_roles": ["Principal Infrastructure Architect"], "work_modes": ["remote"], "minimum_salary": 150000, "target_salary": 180000, "travel_max_percent": 20}})

    def test_profile_preserves_master_resume(self):
        self.assertEqual(self.profile.master_resume, RESUME.strip())
        self.assertTrue(all(f.confidence == "verified" and f.source == "master_resume" for f in self.profile.facts))

    def test_analysis_is_explainable_and_labels_salary(self):
        result = analyze(self.profile, {"title": "Principal Infrastructure Architect", "company": "Acme", "description": JOB})
        self.assertGreater(result["overall_score"], 70)
        self.assertTrue(result["evidence"])
        self.assertEqual(result["compensation"]["employer_posted"]["source"], "employer_posted")
        self.assertIn("azure", result["missing_skills"])
        known = {f.id for f in self.profile.facts}
        self.assertTrue(all(e["fact_id"] in known for e in result["evidence"]))

    def test_tailoring_uses_only_verified_ids(self):
        result = analyze(self.profile, {"title": "Principal Infrastructure Architect", "description": JOB})
        materials = tailor(self.profile, result)
        self.assertTrue(materials["validation"]["valid"])
        self.assertTrue(materials["master_resume_unchanged"])
        self.assertEqual(self.profile.master_resume, RESUME.strip())
        self.assertEqual(materials["change_report"]["before_sha256"], materials["change_report"]["after_sha256"])
        self.assertIn("Selected verified experience", materials["cover_letter"])
        self.assertNotIn("One relevant example", materials["cover_letter"])

    def test_unknown_fact_is_rejected(self):
        self.assertFalse(validate_fact_ids(self.profile, ["fact_invented"])["valid"])

    def test_salary_parser_does_not_call_estimate_posted(self):
        self.assertEqual(extract_salary(JOB)["source"], "employer_posted")

    def test_hourly_salary_is_annualized(self):
        salary = extract_salary("The posted pay range is $48-$82 per hour for this position.")
        self.assertEqual(salary["minimum"], 99840)
        self.assertEqual(salary["maximum"], 170560)

    def test_decimal_hourly_salary_is_annualized_without_dropping_cents(self):
        salary = extract_salary("Pay range: $48.26-$82.21 per hour.")
        self.assertEqual(salary["minimum"], 100381)
        self.assertEqual(salary["maximum"], 170997)

    def test_required_and_preferred_skills_are_not_treated_equally(self):
        job = JOB + " Python is required. Azure experience is preferred."
        result = analyze(self.profile, {"title": "Principal Infrastructure Architect", "description": job})
        self.assertIn("python", result["requirements"]["missing_required_skills"])
        self.assertIn("azure", result["requirements"]["missing_preferred_skills"])
        self.assertEqual(result["recommendation"], "STRETCH")

    def test_two_unmet_required_skills_force_skip(self):
        job = JOB + " Python and Kubernetes are required for all applicants."
        result = analyze(self.profile, {"title": "Principal Infrastructure Architect", "description": job})
        self.assertEqual(set(result["requirements"]["missing_required_skills"]), {"python", "kubernetes"})
        self.assertEqual(result["recommendation"], "SKIP")

    def test_onsite_location_mismatch_is_disqualifying(self):
        profile = build_profile({"name": "Jordan", "master_resume": RESUME, "preferences": {"location": "Raleigh, NC", "work_modes": ["remote", "hybrid"]}})
        result = analyze(profile, {"title": "Architect", "location": "New York, NY", "description": JOB + " This position is hybrid with three days each week in the New York office."})
        self.assertFalse(result["preference_assessment"]["location_match"])
        self.assertEqual(result["recommendation"], "SKIP")
        self.assertTrue(any("does not match your saved location" in item for item in result["disqualifiers"]))

    def test_same_state_different_city_is_not_a_location_match(self):
        profile = build_profile({"name": "Jordan", "master_resume": RESUME, "preferences": {"location": "Raleigh, NC"}})
        result = analyze(profile, {"title": "Architect", "location": "Charlotte, NC", "description": JOB + " This position is on-site in Charlotte."})
        self.assertFalse(result["preference_assessment"]["location_match"])

    def test_remote_role_does_not_fail_for_different_headquarters(self):
        profile = build_profile({"name": "Jordan", "master_resume": RESUME, "preferences": {"location": "Raleigh, NC", "work_modes": ["remote"]}})
        result = analyze(profile, {"title": "Architect", "location": "New York, NY", "description": JOB + " The company is headquartered in New York, but this role is fully remote."})
        self.assertFalse(any("saved location" in item for item in result["disqualifiers"]))

    def test_employment_type_mismatch_is_disqualifying(self):
        profile = build_profile({"name": "Jordan", "master_resume": RESUME, "preferences": {"employment_types": ["full-time"]}})
        result = analyze(profile, {"title": "Architect", "description": JOB + " This is a temporary contract engagement lasting six months."})
        self.assertFalse(result["preference_assessment"]["employment_type_match"])
        self.assertEqual(result["recommendation"], "SKIP")

    def test_required_degree_without_evidence_forces_skip(self):
        result = analyze(self.profile, {"title": "Architect", "description": JOB + " Minimum qualifications: a bachelor's degree is required."})
        self.assertTrue(result["requirements"]["degree_required"])
        self.assertEqual(result["recommendation"], "SKIP")

    def test_java_does_not_match_javascript(self):
        profile = build_profile({"name": "Jordan", "master_resume": RESUME + "Built JavaScript services for internal users.", "preferences": {}})
        result = analyze(profile, {"title": "Engineer", "description": JOB + " Java is required for this engineering position."})
        self.assertIn("java", result["requirements"]["missing_required_skills"])

    def test_wrapped_resume_lines_are_reassembled_with_chronology(self):
        profile = build_profile({"master_resume": """Alex Example\nProfessional Experience\nAcme Corp\nPrincipal Architect | 2022 - Present\n- Led a secure platform modernization across regulated\nenterprise environments with zero unplanned downtime.\nOlder Corp\nEngineer | 2018 - 2021\n- Managed Linux and storage operations for critical systems."""})
        claim = next(f for f in profile.facts if "zero unplanned" in f.text)
        self.assertEqual(claim.start_year, 2022)
        self.assertIn("regulated enterprise environments", claim.text)

    def test_claim_text_cannot_be_embellished_under_valid_id(self):
        fact = self.profile.facts[0]
        result = validate_claims(self.profile, [{"fact_id": fact.id, "text": fact.text + " and doubled revenue"}])
        self.assertFalse(result["valid"])

    def test_pdf_is_paginated_and_well_formed(self):
        pdf = render_pdf("Resume", "\n".join(f"Evidence line {i}" for i in range(110)))
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertGreaterEqual(pdf.count(b"/Type /Page"), 3)
        self.assertTrue(pdf.endswith(b"%%EOF"))

    def test_pdf_hides_internal_evidence_ids(self):
        pdf = render_pdf("Resume", "Jordan Example\nArchitect\n\nEXPERIENCE\n- Verified claim [fact_abcdef1234]", "resume")
        self.assertNotIn(b"fact_abcdef1234", pdf)
        self.assertIn(b"Verified claim", pdf)

    def test_pdf_kind_is_validated(self):
        with self.assertRaises(ValueError):
            render_pdf("Document", "content", "portfolio")

    def test_ai_is_opt_in_and_reports_missing_key(self):
        result = status(AIConfig(True, "test-model", ""))
        self.assertTrue(result["enabled"])
        self.assertFalse(result["ready"])
        self.assertIsNotNone(result["configuration_error"])
        self.assertNotIn("secret", str(result).lower())

    def test_ollama_is_default_ai_provider_and_needs_no_key(self):
        with patch.dict("os.environ", {"CAREER_COPILOT_AI": "true"}, clear=True):
            config = AIConfig.from_env()
        self.assertEqual(config.provider, "ollama")
        self.assertEqual(config.model, "llama3.2")
        self.assertTrue(config.ready)
        self.assertEqual(config.base_url, "http://127.0.0.1:11434/api/chat")

    def test_ollama_uses_local_structured_chat_request(self):
        analysis = analyze(self.profile, {"title": "Architect", "description": JOB})
        fact_id = self.profile.facts[0].id
        def transport(payload, endpoint):
            self.assertEqual(endpoint, "http://127.0.0.1:11434/api/chat")
            self.assertFalse(payload["stream"])
            self.assertEqual(payload["options"]["temperature"], 0)
            self.assertEqual(payload["options"]["num_ctx"], 8192)
            self.assertEqual(payload["options"]["num_predict"], 1200)
            self.assertEqual(payload["format"]["type"], "object")
            value = {"confidence_score": 82, "recommendation": "APPLY", "rationale": "Relevant verified evidence.", "strengths": [{"fact_id": fact_id, "reason": "Relevant."}], "concerns": [], "interview_questions": []}
            return {"message": {"content": __import__("json").dumps(value)}}
        config = AIConfig(True, "llama3.2", "", "ollama", "http://127.0.0.1:11434/api/chat")
        result = assess_fit(self.profile, analysis, config, transport)
        self.assertEqual(result["provider"], "Ollama (local)")

    def test_remote_ollama_url_is_not_ready_for_transport(self):
        from career_copilot.ai import _ollama_transport
        with self.assertRaises(AIError):
            _ollama_transport({}, "http://example.com:11434/api/chat")

    def test_ai_headhunter_cannot_override_a_deterministic_skip(self):
        analysis = analyze(self.profile, {"title": "Architect", "location": "New York, NY", "description": JOB + " This is an on-site role in New York."})
        analysis["recommendation"] = "SKIP"
        analysis["disqualifiers"] = ["Location mismatch"]
        fact_id = self.profile.facts[0].id
        def transport(payload, _key):
            self.assertFalse(payload["store"])
            return {"output_text": __import__("json").dumps({"confidence_score": 94, "recommendation": "PRIORITY APPLY", "rationale": "Strong evidence.", "strengths": [{"fact_id": fact_id, "reason": "Relevant."}], "concerns": [], "interview_questions": []})}
        result = assess_fit(self.profile, analysis, AIConfig(True, "test-model", "secret"), transport)
        self.assertEqual(result["recommendation"], "SKIP")
        self.assertEqual(result["confidence_score"], 39)

    def test_ai_plan_rejects_unknown_evidence(self):
        analysis = analyze(self.profile, {"title": "Architect", "description": JOB})
        def transport(_payload, _key):
            return {"output_text": '{"selected_fact_ids":["fact_invented"],"resume_summary":{"text":"Summary","fact_ids":[]},"cover_letter_opening":{"text":"Opening","fact_ids":[]}}'}
        with self.assertRaises(AIError):
            plan_materials(self.profile, analysis, AIConfig(True, "test-model", "secret"), transport)

    def test_ai_tailoring_runs_generation_and_independent_review(self):
        analysis = analyze(self.profile, {"title": "Architect", "description": JOB})
        fact_id = analysis["evidence"][0]["fact_id"]
        calls = []
        def transport(payload, _key):
            name = payload["text"]["format"]["name"]; calls.append(name)
            if name == "application_material_plan":
                value = {"selected_fact_ids": [fact_id], "resume_summary": {"text": "Evidence-led architecture leader.", "fact_ids": [fact_id]}, "cover_letter_opening": {"text": "My verified experience aligns with this role.", "fact_ids": [fact_id]}}
            else:
                value = {"passed": True, "unsupported_claims": [], "professionalism_score": 91, "review_notes": []}
            return {"output_text": __import__("json").dumps(value)}
        materials = tailor(self.profile, analysis, AIConfig(True, "test-model", "secret"), transport)
        self.assertEqual(calls, ["application_material_plan", "application_material_review"])
        self.assertTrue(materials["ai_generated"])
        self.assertTrue(materials["ai_review"]["passed"])
        self.assertIn("Evidence-led architecture leader.", materials["tailored_resume"])
        self.assertIn("My verified experience aligns", materials["cover_letter"])

    def test_ai_review_failure_blocks_materials(self):
        analysis = analyze(self.profile, {"title": "Architect", "description": JOB})
        fact_id = analysis["evidence"][0]["fact_id"]
        def transport(payload, _key):
            name = payload["text"]["format"]["name"]
            if name == "application_material_plan":
                value = {"selected_fact_ids": [fact_id], "resume_summary": {"text": "Summary", "fact_ids": [fact_id]}, "cover_letter_opening": {"text": "Opening", "fact_ids": [fact_id]}}
            else:
                value = {"passed": False, "unsupported_claims": ["Unsupported claim"], "professionalism_score": 40, "review_notes": ["Remove it"]}
            return {"output_text": __import__("json").dumps(value)}
        with self.assertRaises(ValueError):
            tailor(self.profile, analysis, AIConfig(True, "test-model", "secret"), transport)

    def test_ai_review_rejection_falls_back_to_conservative_draft(self):
        analysis = analyze(self.profile, {"title": "Architect", "company": "Acme", "description": JOB})
        fact_id = analysis["evidence"][0]["fact_id"]
        reviews = 0
        def transport(payload, _key):
            nonlocal reviews
            name = payload["text"]["format"]["name"]
            if name == "application_material_plan":
                value = {"selected_fact_ids": [fact_id], "resume_summary": {"text": "Possibly embellished summary.", "fact_ids": [fact_id]}, "cover_letter_opening": {"text": "Opening", "fact_ids": [fact_id]}}
            else:
                reviews += 1
                value = {"passed": reviews == 2, "unsupported_claims": [] if reviews == 2 else ["Possibly embellished summary."], "professionalism_score": 82, "review_notes": []}
            return {"output_text": __import__("json").dumps(value)}
        materials = tailor(self.profile, analysis, AIConfig(True, "test-model", "secret"), transport)
        self.assertTrue(materials["ai_revision_applied"])
        self.assertTrue(materials["ai_review"]["passed"])
        self.assertIn("Evidence-selected application for Architect at Acme.", materials["tailored_resume"])
        self.assertNotIn("Possibly embellished", materials["tailored_resume"])

    def test_ai_review_sends_only_facts_cited_by_the_draft(self):
        from career_copilot.ai import review_materials
        analysis = analyze(self.profile, {"title": "Architect", "description": JOB})
        analysis["matched_skills"] = []
        cited = self.profile.facts[0]
        def transport(payload, _key):
            supplied = __import__("json").loads(payload["input"])["verified_facts"]
            self.assertEqual(supplied, [{"fact_id": cited.id, "text": cited.text}])
            value = {"passed": True, "unsupported_claims": [], "professionalism_score": 90, "review_notes": []}
            return {"output_text": __import__("json").dumps(value)}
        materials = {"tailored_resume": f"- {cited.text} [{cited.id}]", "cover_letter": "Thank you."}
        result = review_materials(self.profile, analysis, materials, AIConfig(True, "test-model", "secret"), transport)
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
