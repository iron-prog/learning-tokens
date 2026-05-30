"""Talent Angels graph-agent layer for Learning Tokens.

These agents are deterministic Python tools that mirror the mentorship issue's
Locator, Connector, and Pathfinder concepts while remaining easy to test.  They
also include a planner that converts LMS assessment evidence into acquired skill
nodes and Learning Token recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .preview import build_preview
from .talent_graph import GraphPath, LocatedNode, TalentGraph

DEFAULT_GRAPH_PATH = Path(__file__).resolve().parents[1] / "data" / "talent_graph_seed.json"


@dataclass(frozen=True)
class AgentResponse:
    """Serializable agent response with enough context for a chat UI."""

    agent: str
    query: str
    result: Mapping[str, Any]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "query": self.query,
            "result": dict(self.result),
            "explanation": self.explanation,
        }


class LocatorAgent:
    """Find exact or likely positions of skills, tasks, and occupations."""

    name = "locator"

    def __init__(self, graph: TalentGraph):
        self.graph = graph

    def run(
        self,
        query: str,
        *,
        kinds: Iterable[str] | None = None,
        taxonomies: Iterable[str] | None = None,
        limit: int = 5,
    ) -> AgentResponse:
        matches = self.graph.locate(query, kinds=kinds, taxonomies=taxonomies, limit=limit)
        explanation = f"Located {len(matches)} graph node(s) matching {query!r}."
        return AgentResponse(
            agent=self.name,
            query=query,
            result={"matches": [match.to_dict() for match in matches]},
            explanation=explanation,
        )


class ConnectorAgent:
    """List predecessor and successor nodes around a graph location."""

    name = "connector"

    def __init__(self, graph: TalentGraph):
        self.graph = graph

    def run(self, node_id: str, *, direction: str = "both", relations: Iterable[str] | None = None) -> AgentResponse:
        node = self.graph.get(node_id)
        neighbors = self.graph.neighbors(node_id, direction=direction, relations=relations)
        predecessor_count = len(neighbors["predecessors"])
        successor_count = len(neighbors["successors"])
        return AgentResponse(
            agent=self.name,
            query=node_id,
            result={"node": node.to_dict(), **neighbors},
            explanation=(
                f"Found {predecessor_count} predecessor(s) and {successor_count} successor(s) "
                f"around {node.label}."
            ),
        )


class PathfinderAgent:
    """Trace possible learning journeys between two graph locations."""

    name = "pathfinder"

    def __init__(self, graph: TalentGraph):
        self.graph = graph

    def run(
        self,
        start_id: str,
        end_id: str,
        *,
        max_depth: int = 4,
        limit: int = 5,
        relations: Iterable[str] | None = None,
    ) -> AgentResponse:
        paths = self.graph.shortest_paths(start_id, end_id, max_depth=max_depth, limit=limit, relations=relations)
        return AgentResponse(
            agent=self.name,
            query=f"{start_id} -> {end_id}",
            result={"paths": [path.to_dict() for path in paths]},
            explanation=f"Found {len(paths)} path(s) from {start_id} to {end_id} within depth {max_depth}.",
        )


class LearningTokenPlannerAgent:
    """Connect normalized LMS evidence with the talent graph and issuance preview."""

    name = "learning-token-planner"

    def __init__(self, graph: TalentGraph):
        self.graph = graph

    def infer_acquired_skills(self, preview: Mapping[str, Any], *, token_types: Iterable[str] = ("score",)) -> list[str]:
        accepted_token_types = {token_type for token_type in token_types}
        skill_ids: set[str] = set()
        for issuance in preview.get("issuances", []) or []:
            if issuance.get("tokenType") not in accepted_token_types:
                continue
            evidence = issuance.get("evidence", {}) or {}
            searchable = " ".join(
                str(value)
                for key, value in evidence.items()
                if key in {"assignmentTitle", "assignment.title", "skill", "competency"} and value
            )
            for match in self.graph.locate(searchable, kinds=["skill"], limit=3):
                if match.score >= 0.45:
                    skill_ids.add(match.node.id)
        return sorted(skill_ids)

    def run(
        self,
        payload: Mapping[str, Any],
        policy: Mapping[str, Any],
        *,
        target_kind: str = "occupation",
        recommendation_limit: int = 5,
    ) -> AgentResponse:
        preview = build_preview(payload, policy)
        acquired_skill_ids = self.infer_acquired_skills(preview)
        recommendations = self.graph.recommend_from_skills(
            acquired_skill_ids,
            target_kind=target_kind,
            limit=recommendation_limit,
        )
        return AgentResponse(
            agent=self.name,
            query=str((payload.get("course") or {}).get("id", "unknown-course")),
            result={
                "preview": preview,
                "acquiredSkillIds": acquired_skill_ids,
                "recommendations": recommendations,
            },
            explanation=(
                f"Generated {preview['summary']['totalIssuances']} issuance candidate(s), "
                f"mapped them to {len(acquired_skill_ids)} acquired skill node(s), and ranked "
                f"{len(recommendations)} {target_kind} recommendation(s)."
            ),
        )


def load_default_graph() -> TalentGraph:
    """Load the repository's seed graph for local agent demos and tests."""

    return TalentGraph.from_json(DEFAULT_GRAPH_PATH)


def serialize_paths(paths: Iterable[GraphPath]) -> list[dict[str, Any]]:
    return [path.to_dict() for path in paths]


def serialize_locations(locations: Iterable[LocatedNode]) -> list[dict[str, Any]]:
    return [location.to_dict() for location in locations]
