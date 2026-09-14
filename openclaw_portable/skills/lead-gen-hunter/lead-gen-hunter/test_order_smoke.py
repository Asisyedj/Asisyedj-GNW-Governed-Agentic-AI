import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).with_name("lead_gen_hunter.py")
spec = importlib.util.spec_from_file_location("lead_gen_hunter", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestOrderSmoke(unittest.TestCase):
    def test_sqlite_id_round_trip_and_enrichment_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = module.LeadDatabase(str(Path(tmp) / "leads.db"))
            lead = module.Lead(name="Ada Lovelace", company="Analytical Engines", source="fixture", icp_score=90)
            self.assertTrue(db.insert_lead(lead))
            self.assertIsInstance(lead.id, int)
            selected = db.get_qualified_leads()[0]
            self.assertEqual(selected.id, lead.id)
            module.ContactEnricher().enrich(selected)
            self.assertTrue(db.update_lead(selected))
            selected_again = db.get_qualified_leads()[0]
            self.assertEqual(selected_again.id, lead.id)
            self.assertEqual(selected_again.email_status, "guessed")
            self.assertEqual(selected_again.linkedin_status, "guessed")

    def test_network_is_disabled_by_default(self):
        connector = module.GitHubConnector()
        connector.session.get = Mock(side_effect=AssertionError("network call"))
        self.assertEqual(connector.search("fixture"), [])
        enricher = module.ContactEnricher(hunter_api_key="secret")
        enricher.session.get = Mock(side_effect=AssertionError("network call"))
        lead = module.Lead(name="Ada Lovelace", company="Analytical Engines")
        enricher.enrich(lead)
        self.assertFalse(enricher.session.get.called)
        self.assertEqual(lead.email_status, "guessed")

    def test_hunter_secret_is_not_in_query_params(self):
        enricher = module.ContactEnricher(hunter_api_key="secret", allow_network=True)
        response = Mock(status_code=200)
        response.json.return_value = {"data": {"email": "ada@example.test"}}
        enricher.session.get = Mock(return_value=response)
        self.assertEqual(enricher._hunter_lookup("Ada Lovelace", "analytical.com"), "ada@example.test")
        _, kwargs = enricher.session.get.call_args
        self.assertNotIn("api_key", kwargs.get("params", {}))
        self.assertEqual(kwargs["headers"]["X-API-Key"], "secret")

    def test_csv_formula_neutralization_and_no_example_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = module.LeadDatabase(str(Path(tmp) / "leads.db"))
            lead = module.Lead(name="=SUM(1,1)", company="Acme", source="fixture", title="CEO", icp_score=90)
            db.insert_lead(lead)
            hunter = module.LeadGenHunter(db_path=str(Path(tmp) / "leads2.db"))
            hunter.db = db
            output = Path(tmp) / "out.csv"
            hunter.export_for_client_manager(str(output))
            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["name"], "'=SUM(1,1)")
            self.assertEqual(rows[0]["email"], "")
            self.assertEqual(rows[0]["email_status"], "unknown")
            self.assertNotIn("example.com", output.read_text())
            with self.assertRaises(FileExistsError):
                hunter.export_for_client_manager(str(output))

    def test_config_validation_rejects_bad_schema(self):
        with self.assertRaises(ValueError):
            module.validate_icp_config({"titles": []})
        with self.assertRaises(ValueError):
            module.validate_intent_config([{"pattern": "[", "weight": 1, "type": "bad"}])


if __name__ == "__main__":
    unittest.main()
