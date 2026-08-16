import unittest

from career_copilot.analyzer import analyze, extract_salary
from career_copilot.profile import build_profile
from career_copilot.tailor import tailor
from career_copilot.validator import validate_fact_ids


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

    def test_unknown_fact_is_rejected(self):
        self.assertFalse(validate_fact_ids(self.profile, ["fact_invented"])["valid"])

    def test_salary_parser_does_not_call_estimate_posted(self):
        self.assertEqual(extract_salary(JOB)["source"], "employer_posted")


if __name__ == "__main__":
    unittest.main()
