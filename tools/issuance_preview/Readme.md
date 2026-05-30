# Learning Tokens Python tools: issuance previews and Talent Angels graph agents

This directory contains a dependency-free Python feature for the Learning Tokens repository. It now covers two connected workflows:

1. **Issuance preview**: turn a normalized LMS payload from `npm_package ltsdk` into deterministic Learning Token issuance candidates before any blockchain mint or transfer.
2. **Talent Angels graph agents**: browse a local skills/tasks/occupations graph with Locator, Connector, Pathfinder, and a Learning Token planner agent inspired by the LFX mentorship project.

The upstream Learning Tokens repo describes Learning Tokens as a mechanism for recognizing and certifying skills acquisition. The Talent Angels mentorship expands that direction with AI Graph Agents over taxonomies such as ESCO, O*NET, SFIA, BLS, and Lightcast. This feature adds the first local, testable graph-agent layer that can later be connected to larger taxonomy datasets, GraphRAG, or a chat UI.

## Package layout

```text
tools/issuance_preview/
├── data/talent_graph_seed.json              # local demo graph for skills, tasks, occupations, assessments
├── learning_tokens_issuance/
│   ├── agents.py                            # Locator, Connector, Pathfinder, LearningTokenPlanner
│   ├── preview.py                           # issuance preview engine and CLI
│   └── talent_graph.py                      # graph primitives, search, neighbors, paths, recommendations
└── tests/
    ├── test_preview.py
    └── test_talent_agents.py
```

## Issuance policy format

A policy contains the target course, optional learner wallet mappings, and token rules. Each rule describes a token type, an amount, optional assignment filters, and a condition over normalized LMS evidence.

```json
{
  "courseId": "1001",
  "wallets": {
    "21": "0x1111111111111111111111111111111111111111"
  },
  "tokens": [
    {
      "id": "attendance-submitted",
      "tokenType": "attendance",
      "amount": 1,
      "condition": {
        "field": "submission.workflow_state",
        "equals": "submitted"
      }
    },
    {
      "id": "score-above-80",
      "tokenType": "score",
      "amount": 10,
      "condition": {
        "field": "grade.percentage",
        "gte": 80
      }
    }
  ]
}
```

Conditions support `equals`, `notEquals`, `in`, `gt`, `gte`, `lt`, `lte`, `exists`, and nested `all` / `any` groups. Field paths are evaluated against `course`, `learner`, `assignment`, `submission`, and `grade` records from the normalized payload.

## Talent Angels graph agents

The seed graph is intentionally small, but it models the same shape as the intended mentorship work:

- **Locator** identifies graph nodes for a natural-language query.
- **Connector** returns predecessor and successor nodes around a selected graph location.
- **Pathfinder** traces possible routes between two graph locations.
- **LearningTokenPlanner** combines issuance previews with the graph to infer acquired skills and rank learning/career recommendations.

The seed data includes example nodes from ESCO, O*NET, SFIA, BLS, Lightcast, and Learning Tokens. It is not a replacement for the official datasets; it is a lightweight fixture that makes the architecture runnable and testable in this repo.

## CLI examples

### Preview Learning Token issuance

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance preview \
  --payload npm_package\ ltsdk/tests/fixtures/moodle-normalized.json \
  --policy /path/to/policy.json \
  --pretty
```

The previous top-level form is still supported for compatibility:

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance \
  --payload npm_package\ ltsdk/tests/fixtures/moodle-normalized.json \
  --policy /path/to/policy.json \
  --pretty
```

### Locate skills, tasks, or occupations

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance locate "knowledge graph" --kind skill --pretty
```

### Connect a graph node to neighbors

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance connect esco:skill:knowledge-graphs --pretty
```

### Find a learning path

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance path \
  learning-token:course:graph-agents \
  onet:task:build-ontology \
  --max-depth 4 \
  --pretty
```

### Plan token issuance plus talent recommendations

```bash
python3 -m tools.issuance_preview.learning_tokens_issuance plan \
  --payload npm_package\ ltsdk/tests/fixtures/moodle-normalized.json \
  --policy /path/to/policy.json \
  --pretty
```

## Python API

```python
from tools.issuance_preview.learning_tokens_issuance import (
    LearningTokenPlannerAgent,
    LocatorAgent,
    load_default_graph,
)

payload = {...}  # normalized LMS payload from LTSDK
policy = {...}   # scoring-guide-style token rules

graph = load_default_graph()
print(LocatorAgent(graph).run("graph search", kinds=["skill"]).to_dict())
print(LearningTokenPlannerAgent(graph).run(payload, policy).to_dict())
```

## Test

```bash
python3 -m unittest discover -s tools/issuance_preview/tests
```
