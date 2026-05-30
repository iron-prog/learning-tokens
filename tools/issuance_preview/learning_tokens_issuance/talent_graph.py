"""Knowledge-graph primitives for Talent Angels skill navigation.

The LFX Talent Angels mentorship describes three graph agents over global
skills, tasks, and occupations taxonomies: Locator, Connector, and Pathfinder.
This module keeps the first implementation intentionally local and
serializable so it can run in CI, notebooks, or a future API server without a
vector database or graph database dependency.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

TokenSet = set[str]


@dataclass(frozen=True)
class TalentNode:
    """A normalized node in a talent ontology.

    Nodes can represent skills, tasks, occupations, learning resources, or
    assessment signals.  The `taxonomy` field keeps the source vocabulary
    visible (for example ESCO, O*NET, SFIA, BLS, or Lightcast), while `aliases`
    make natural-language lookup forgiving enough for a first agentic workflow.
    """

    id: str
    label: str
    kind: str
    taxonomy: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def search_text(self) -> str:
        return " ".join([self.id, self.label, self.kind, self.taxonomy, self.description, *self.aliases])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "taxonomy": self.taxonomy,
            "description": self.description,
            "aliases": list(self.aliases),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TalentEdge:
    """A directed relation between two talent ontology nodes."""

    source: str
    target: str
    relation: str
    weight: float = 1.0
    evidence: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
            "evidence": self.evidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LocatedNode:
    """A ranked locator result."""

    node: TalentNode
    score: float
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = self.node.to_dict()
        payload.update({"score": self.score, "matchedTerms": list(self.matched_terms)})
        return payload


@dataclass(frozen=True)
class GraphPath:
    """A path through the talent graph."""

    nodes: tuple[TalentNode, ...]
    edges: tuple[TalentEdge, ...]
    total_weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalWeight": self.total_weight,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> TokenSet:
    """Return normalized alphanumeric tokens for simple semantic matching."""

    return set(_WORD_RE.findall(text.lower()))


class TalentGraph:
    """In-memory directed graph for skills, tasks, and occupations."""

    def __init__(self, nodes: Iterable[TalentNode], edges: Iterable[TalentEdge]):
        self.nodes: dict[str, TalentNode] = {node.id: node for node in nodes}
        self.edges: list[TalentEdge] = list(edges)
        self._outgoing: dict[str, list[TalentEdge]] = {node_id: [] for node_id in self.nodes}
        self._incoming: dict[str, list[TalentEdge]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            if edge.source not in self.nodes:
                raise ValueError(f"Edge source {edge.source!r} is not a known node")
            if edge.target not in self.nodes:
                raise ValueError(f"Edge target {edge.target!r} is not a known node")
            self._outgoing.setdefault(edge.source, []).append(edge)
            self._incoming.setdefault(edge.target, []).append(edge)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TalentGraph":
        nodes = [
            TalentNode(
                id=str(item["id"]),
                label=str(item["label"]),
                kind=str(item.get("kind", "skill")),
                taxonomy=str(item.get("taxonomy", "local")),
                description=str(item.get("description", "")),
                aliases=tuple(str(alias) for alias in item.get("aliases", []) or []),
                metadata=item.get("metadata", {}) or {},
            )
            for item in payload.get("nodes", [])
        ]
        edges = [
            TalentEdge(
                source=str(item["source"]),
                target=str(item["target"]),
                relation=str(item.get("relation", "related_to")),
                weight=float(item.get("weight", 1.0)),
                evidence=str(item.get("evidence", "")),
                metadata=item.get("metadata", {}) or {},
            )
            for item in payload.get("edges", [])
        ]
        return cls(nodes, edges)

    @classmethod
    def from_json(cls, path: str | Path) -> "TalentGraph":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [self.nodes[node_id].to_dict() for node_id in sorted(self.nodes)],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def get(self, node_id: str) -> TalentNode:
        return self.nodes[node_id]

    def locate(
        self,
        query: str,
        *,
        kinds: Iterable[str] | None = None,
        taxonomies: Iterable[str] | None = None,
        limit: int = 5,
    ) -> list[LocatedNode]:
        """Locate likely graph nodes for a natural-language query."""

        query_terms = tokenize(query)
        if not query_terms:
            return []
        allowed_kinds = {kind.lower() for kind in kinds or []}
        allowed_taxonomies = {taxonomy.lower() for taxonomy in taxonomies or []}
        matches: list[LocatedNode] = []
        for node in self.nodes.values():
            if allowed_kinds and node.kind.lower() not in allowed_kinds:
                continue
            if allowed_taxonomies and node.taxonomy.lower() not in allowed_taxonomies:
                continue
            node_terms = tokenize(node.search_text())
            overlap = query_terms & node_terms
            if not overlap:
                continue
            exact_bonus = 1.0 if query.lower() in node.search_text().lower() else 0.0
            score = (len(overlap) / max(len(query_terms), 1)) + exact_bonus
            matches.append(LocatedNode(node=node, score=round(score, 4), matched_terms=tuple(sorted(overlap))))
        return sorted(matches, key=lambda item: (-item.score, item.node.taxonomy, item.node.label))[:limit]

    def neighbors(self, node_id: str, *, direction: str = "both", relations: Iterable[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        """Return predecessor and successor nodes around a node."""

        if node_id not in self.nodes:
            raise KeyError(f"Unknown node id: {node_id}")
        allowed_relations = {relation for relation in relations or []}

        def include(edge: TalentEdge) -> bool:
            return not allowed_relations or edge.relation in allowed_relations

        result: dict[str, list[dict[str, Any]]] = {"predecessors": [], "successors": []}
        if direction in ("incoming", "both"):
            for edge in self._incoming.get(node_id, []):
                if include(edge):
                    result["predecessors"].append({"edge": edge.to_dict(), "node": self.nodes[edge.source].to_dict()})
        if direction in ("outgoing", "both"):
            for edge in self._outgoing.get(node_id, []):
                if include(edge):
                    result["successors"].append({"edge": edge.to_dict(), "node": self.nodes[edge.target].to_dict()})
        return result

    def shortest_paths(
        self,
        start_id: str,
        end_id: str,
        *,
        max_depth: int = 4,
        limit: int = 5,
        relations: Iterable[str] | None = None,
    ) -> list[GraphPath]:
        """Trace possible routes between two graph locations using BFS."""

        if start_id not in self.nodes:
            raise KeyError(f"Unknown start node id: {start_id}")
        if end_id not in self.nodes:
            raise KeyError(f"Unknown end node id: {end_id}")
        allowed_relations = {relation for relation in relations or []}
        paths: list[GraphPath] = []
        queue = deque([(start_id, tuple([start_id]), tuple())])
        while queue and len(paths) < limit:
            current_id, visited, edge_path = queue.popleft()
            if len(edge_path) > max_depth:
                continue
            if current_id == end_id and edge_path:
                node_path = tuple(self.nodes[node_id] for node_id in visited)
                paths.append(
                    GraphPath(
                        nodes=node_path,
                        edges=edge_path,
                        total_weight=round(sum(edge.weight for edge in edge_path), 4),
                    )
                )
                continue
            if len(edge_path) == max_depth:
                continue
            for edge in self._outgoing.get(current_id, []):
                if allowed_relations and edge.relation not in allowed_relations:
                    continue
                if edge.target in visited:
                    continue
                queue.append((edge.target, (*visited, edge.target), (*edge_path, edge)))
        return paths

    def recommend_from_skills(
        self,
        acquired_skill_ids: Iterable[str],
        *,
        target_kind: str = "occupation",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Rank target nodes by how much of their incoming skill evidence is covered."""

        acquired = {node_id for node_id in acquired_skill_ids if node_id in self.nodes}
        recommendations: list[dict[str, Any]] = []
        for node in self.nodes.values():
            if node.kind != target_kind:
                continue
            required_edges = [edge for edge in self._incoming.get(node.id, []) if edge.relation in {"enables", "requires"}]
            if not required_edges:
                continue
            required = {edge.source for edge in required_edges}
            covered = sorted(required & acquired)
            missing = sorted(required - acquired)
            coverage = len(covered) / len(required)
            recommendations.append(
                {
                    "node": node.to_dict(),
                    "coverage": round(coverage, 4),
                    "coveredSkillIds": covered,
                    "missingSkillIds": missing,
                }
            )
        return sorted(recommendations, key=lambda item: (-item["coverage"], len(item["missingSkillIds"]), item["node"]["label"]))[:limit]
