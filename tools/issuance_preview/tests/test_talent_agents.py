import json
import tempfile
import unittest
from pathlib import Path

from tools.issuance_preview.learning_tokens_issuance import (
    ConnectorAgent,
    LearningTokenPlannerAgent,
    LocatorAgent,
    PathfinderAgent,
    TalentGraph,
    load_default_graph,
    main,
)

ROOT = Path(__file__).resolve().parents[3]
MOODLE_FIXTURE = ROOT / "npm_package ltsdk" / "tests" / "fixtures" / "moodle-normalized.json"


class TalentGraphAgentTests(unittest.TestCase):
    def setUp(self):
        self.graph = load_default_graph()

    def test_seed_graph_loads_taxonomy_nodes_and_edges(self):
        self.assertIn("esco:skill:knowledge-graphs", self.graph.nodes)
        self.assertIn("onet:occupation:data-scientist", self.graph.nodes)
        self.assertGreaterEqual(len(self.graph.edges), 10)

        exported = self.graph.to_dict()
        reloaded = TalentGraph.from_dict(exported)
        self.assertEqual(set(reloaded.nodes), set(self.graph.nodes))

    def test_locator_agent_finds_knowledge_graph_skill(self):
        response = LocatorAgent(self.graph).run("knowledge graph", kinds=["skill"], limit=3).to_dict()

        self.assertEqual(response["agent"], "locator")
        self.assertGreaterEqual(len(response["result"]["matches"]), 1)
        self.assertEqual(response["result"]["matches"][0]["id"], "esco:skill:knowledge-graphs")

    def test_connector_agent_returns_predecessors_and_successors(self):
        response = ConnectorAgent(self.graph).run("esco:skill:knowledge-graphs").to_dict()

        self.assertEqual(response["agent"], "connector")
        self.assertEqual(response["result"]["node"]["id"], "esco:skill:knowledge-graphs")
        predecessor_ids = {item["node"]["id"] for item in response["result"]["predecessors"]}
        successor_ids = {item["node"]["id"] for item in response["result"]["successors"]}
        self.assertIn("learning-token:course:graph-agents", predecessor_ids)
        self.assertIn("lightcast:skill:graph-search", successor_ids)

    def test_pathfinder_agent_traces_learning_journey(self):
        response = PathfinderAgent(self.graph).run(
            "learning-token:course:graph-agents",
            "onet:task:build-ontology",
            max_depth=4,
            limit=3,
        ).to_dict()

        self.assertEqual(response["agent"], "pathfinder")
        paths = response["result"]["paths"]
        self.assertGreaterEqual(len(paths), 1)
        first_node_ids = [node["id"] for node in paths[0]["nodes"]]
        self.assertEqual(first_node_ids[0], "learning-token:course:graph-agents")
        self.assertEqual(first_node_ids[-1], "onet:task:build-ontology")

    def test_recommendations_rank_occupations_from_acquired_skills(self):
        recs = self.graph.recommend_from_skills(["lightcast:skill:python", "sfia:skill:machine-learning"])

        self.assertGreaterEqual(len(recs), 1)
        labels = [item["node"]["label"] for item in recs]
        self.assertIn("Data Scientist", labels)
        data_scientist = next(item for item in recs if item["node"]["label"] == "Data Scientist")
        self.assertIn("sfia:skill:machine-learning", data_scientist["coveredSkillIds"])

    def test_learning_token_planner_combines_preview_and_graph_recommendations(self):
        payload = json.loads(MOODLE_FIXTURE.read_text(encoding="utf-8"))
        payload["learners"][0]["assignments"][0]["title"] = "Knowledge graphs pathfinder project"
        policy = {
            "courseId": "1001",
            "wallets": {"21": "0x1111111111111111111111111111111111111111"},
            "tokens": [
                {
                    "id": "score-graph-project",
                    "tokenType": "score",
                    "amount": 10,
                    "condition": {"field": "grade.percentage", "gte": 80},
                }
            ],
        }

        response = LearningTokenPlannerAgent(self.graph).run(payload, policy).to_dict()

        self.assertEqual(response["agent"], "learning-token-planner")
        self.assertEqual(response["result"]["preview"]["summary"]["totalIssuances"], 1)
        self.assertIn("esco:skill:knowledge-graphs", response["result"]["acquiredSkillIds"])
        self.assertGreaterEqual(len(response["result"]["recommendations"]), 1)

    def test_cli_locator_and_path_commands_write_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            locate_path = Path(tmp) / "locate.json"
            path_path = Path(tmp) / "path.json"

            locate_exit = main(["locate", "python", "--kind", "skill", "--out", str(locate_path), "--pretty"])
            path_exit = main([
                "path",
                "learning-token:course:graph-agents",
                "onet:task:build-ontology",
                "--out",
                str(path_path),
                "--pretty",
            ])

            self.assertEqual(locate_exit, 0)
            self.assertEqual(path_exit, 0)
            locate_payload = json.loads(locate_path.read_text(encoding="utf-8"))
            path_payload = json.loads(path_path.read_text(encoding="utf-8"))
            self.assertEqual(locate_payload["agent"], "locator")
            self.assertEqual(path_payload["agent"], "pathfinder")
            self.assertGreaterEqual(len(path_payload["result"]["paths"]), 1)


if __name__ == "__main__":
    unittest.main()
