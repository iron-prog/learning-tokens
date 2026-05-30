# Talent Angels Examples

## Locator

python -m tools.issuance_preview.learning_tokens_issuance.main \
locate "knowledge graph" \
--kind skill \
--pretty

## Connector

python -m tools.issuance_preview.learning_tokens_issuance.main \
connect "esco:skill:knowledge-graphs" \
--pretty

## Pathfinder

python -m tools.issuance_preview.learning_tokens_issuance.main \
path \
"lightcast:skill:python" \
"bls:occupation:software-developer" \
--pretty

## Preview

python -m tools.issuance_preview.learning_tokens_issuance.main \
preview \
--payload examples/talent-angels-moodle.json \
--policy examples/policy.json \
--pretty

## Planner

python -m tools.issuance_preview.learning_tokens_issuance.main \
plan \
--payload examples/talent-angels-moodle.json \
--policy examples/policy.json \
--pretty