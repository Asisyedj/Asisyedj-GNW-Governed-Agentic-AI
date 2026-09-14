import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parent
    / "openclaw"
    / "oc-050-scientific-research-orchestrator"
    / "research_orchestrator.py"
)
_spec = importlib.util.spec_from_file_location("research_orchestrator", MODULE_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class FakeProvider:
    def __init__(self, papers):
        self.papers = papers
        self.calls = []

    async def search(self, query, limit=20):
        self.calls.append((query, limit))
        return list(self.papers)


class ResearchOrchestratorSmokeTests(unittest.TestCase):
    def test_order_smoke_is_offline_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = _module.ResearchOrchestrator(tmp)
            first = _module.Paper(
                id="provider-a:one",
                title="Same study",
                authors=["Ada Lovelace"],
                abstract="This study demonstrates a useful result.",
                year=2025,
                source="semantic_scholar",
                doi="10.1234/ABC",
                url="https://doi.org/10.1234/ABC",
            )
            duplicate = _module.Paper(
                id="provider-b:two",
                title="Same study from another provider",
                authors=["Ada Lovelace"],
                abstract="This study demonstrates a useful result.",
                year=2025,
                source="pubmed",
                doi="https://doi.org/10.1234/abc",
            )
            second = _module.Paper(
                id="provider-b:three",
                title="Different study",
                authors=["Grace Hopper"],
                abstract="This study finds a different result.",
                year=2024,
                source="arxiv",
                url="https://arxiv.org/abs/1234.5678",
            )
            providers = [FakeProvider([first]), FakeProvider([duplicate, second])]
            orchestrator.semantic_scholar, orchestrator.arxiv = providers

            papers = asyncio.run(
                orchestrator.search("offline query", sources=["semantic_scholar", "arxiv"], limit=1)
            )
            self.assertEqual(len(papers), 1)
            self.assertEqual(providers[0].calls, [("offline query", 1)])
            self.assertEqual(providers[1].calls, [("offline query", 1)])
            self.assertTrue((Path(tmp) / "papers.json").exists())
            self.assertTrue((Path(tmp) / "audit.jsonl").exists())

    def test_provider_ids_and_bibtex_are_stable_and_escaped(self):
        item = {
            "paperId": "S2-123",
            "title": "A {safe} & useful study_",
            "authors": [{"name": "Ada Lovelace"}],
            "abstract": "Abstract",
            "year": 2025,
            "externalIds": {"DOI": "10.1234/test"},
            "url": "https://example.test/paper",
            "citationCount": 3,
        }
        parsed_a = _module.SemanticScholarConnector()._parse_results([item])[0]
        parsed_b = _module.SemanticScholarConnector()._parse_results([item])[0]
        self.assertEqual(parsed_a.id, parsed_b.id)
        bibtex = _module.CitationFormatter.format_bibtex(parsed_a)
        self.assertIn("doi = {10.1234/test}", bibtex)
        self.assertIn("A \\{safe\\} \\& useful study\\_", bibtex)
        self.assertNotIn(",\n  doi", bibtex.split("}", 1)[0])

    def test_analysis_is_explicitly_draft_and_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = _module.ResearchOrchestrator(tmp)
            paper = _module.Paper(
                id="internal:paper",
                title="Offline paper",
                authors=["Test Author"],
                abstract="This study demonstrates a result.",
                year=2025,
                source="internal",
            )
            orchestrator.papers[paper.id] = paper
            project = orchestrator.create_project("Offline", "testing")
            self.assertTrue(orchestrator.add_to_project(project.id, [paper.id]))
            report = asyncio.run(orchestrator.analyze_project(project.id))
            self.assertEqual(report["analysis_status"], "draft")
            self.assertEqual(report["publication_status"], "not_published")
            self.assertFalse(report["published"])
            stored = orchestrator.get_project_report(project.id)
            self.assertEqual(stored["analysis_status"], "draft")


if __name__ == "__main__":
    unittest.main()


__all__ = ["ResearchOrchestratorSmokeTests"]

