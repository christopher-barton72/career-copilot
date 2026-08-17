import unittest
from career_copilot.analyzer import analyze, extract_salary
from career_copilot.profile import build_profile
from career_copilot.resume_pdf import build_resume_pdf
from career_copilot.tailor import tailor
from career_copilot.validator import validate_fact_ids

RESUME="""Jordan Example
Principal Infrastructure Architect
2018-Present - Led enterprise storage architecture using NetApp, Pure, VMware, and S3.
Designed Zero Trust controls aligned with NIST for regulated environments.
Mentored engineering teams and presented technology strategy to executives.
Delivered major platform migrations with no unplanned customer downtime.
B.S. Information Systems - Example University
"""
JOB="""We seek a Principal Infrastructure Architect to lead enterprise storage and security architecture. The successful candidate will use NetApp, VMware, S3, NIST, and Zero Trust practices, mentor engineers, and present strategy to leadership. This remote role pays $160,000 - $195,000 and requires 10% travel. Azure experience is preferred. Candidates collaborate across security and infrastructure teams."""
class CoreTests(unittest.TestCase):
    def setUp(self): self.profile=build_profile({"name":"Jordan Example","headline":"Principal Infrastructure Architect","master_resume":RESUME,"preferences":{"target_roles":["Principal Infrastructure Architect"],"target_skills":["NIST"],"work_modes":["remote"],"minimum_salary":150000,"target_salary":180000,"travel_max_percent":20}})
    def test_master_immutable(self): self.assertEqual(self.profile.master_resume,RESUME.strip())
    def test_analysis(self):
        r=analyze(self.profile,{"title":"Principal Infrastructure Architect","company":"Acme","description":JOB}); self.assertGreater(r["overall_score"],70); self.assertIn("azure",r["missing_skills"]); self.assertEqual(extract_salary(JOB)["source"],"employer_posted")
    def test_structured_tailoring_and_pdf(self):
        original=self.profile.master_resume; m=tailor(self.profile,analyze(self.profile,{"title":"Principal Infrastructure Architect","company":"Acme","description":JOB})); self.assertTrue(m["validation"]["valid"]); self.assertTrue(m["resume"]["summary"]); self.assertTrue(m["change_log"]); self.assertTrue(all(x["status"]=="verified" for x in m["claim_ledger"])); self.assertEqual(self.profile.master_resume,original); pdf=build_resume_pdf(m); self.assertTrue(pdf.startswith(b"%PDF-1.4")); self.assertIn(b"EXECUTIVE PROFILE",pdf); self.assertGreater(len(pdf),1500)
    def test_unknown_fact_rejected(self): self.assertFalse(validate_fact_ids(self.profile,["fact_invented"])["valid"])
if __name__=="__main__": unittest.main()

