# Reconciliation contract fixtures v1

These JSON files are language-independent golden cases for ADR-0002. A conforming
implementation must produce the exact result represented by every fixture.

Each fixture contains:

- `base_revision` and `target_revision`;
- `allocator_next_id`, the first runtime identity available for new nodes;
- a previous committed tree with runtime IDs, or `null` for initial mount;
- a declarative candidate tree without runtime IDs;
- an expected mutation batch and committed tree, or a typed validation error.

`name` and `expected` belong only to the executable test wrapper. They are not part of
the runtime reconciliation request, whose closed fields are contract version, revisions,
allocator state, previous tree, candidate tree and optional defensive-limit overrides.

Properties use decimal `PropertyId` strings. Values are closed tagged objects such as
`{"type": "string", "value": "Hello"}`. `schema/components.json` is the executable
registry for the supported `View` and `Text` properties. A property must exist for the
specific component and its tagged value must match the registered type before diffing.
Names in this provisional registry document semantics; numeric IDs are the wire contract.

Run the executable specification:

```bash
python3 scripts/check_reconciliation_fixtures.py
python3 scripts/check_reconciliation_sequences.py
```

The executable specification is split by responsibility:

- `reconciliation_validation.py` owns schemas, envelopes, limits and tree invariants;
- `reconciliation_oracle.py` owns matching, mutation ordering and committed output;
- `reconciliation_batch_model.py` independently applies host mutations and checks the
  resulting host-visible tree;
- `check_reconciliation_fixtures.py` only discovers fixtures, executes and reports.

The host model compares runtime identity, component kind, properties and ordered children.
Declarative keys are intentionally excluded: they are reconciliation metadata and no v1
host mutation carries them. This prevents the checker from inventing host state that the
batch cannot reproduce.

The Python oracle is a specification aid, not production runtime code. Rust remains the
authoritative implementation target. Contract changes require a new version directory
or an ADR that explains backward compatibility.

Candidate nodes are closed objects containing exactly `kind`, `key`, `properties` and
`children`. Unknown fields, missing fields and invalid field types fail before identity
allocation. The default direct-child limit is 10,000 and can be lowered per fixture.

The transaction envelope is also fail-closed. Revisions are non-negative and advance by
exactly one, the next allocator identity is positive, and limit overrides may only lower
or replace known positive integer limits. These checks run before candidate validation.

A previous committed tree is revalidated before reuse. Its revision and node structure
are closed, every `NodeId` is a unique positive integer, sibling keys remain unique and
the allocator must be strictly greater than the maximum committed identity.

Version 1 currently covers initial mount, property set/removal and validation, component
schema enforcement, keyed movement, component-kind replacement, subtree deletion,
duplicate keys, stale revisions, malformed nodes, and defensive limits for strings,
depth, direct children, total nodes and operation count. The suite contains 31 fixtures,
supplemented by deterministic generated stateful sequences. Fixed seeds make failures
reproducible; generated coverage complements rather than replaces the reviewed golden cases.
The sampler uses only the standard generator's documented `random()` compatibility promise
and implements its own bounded selection and shuffle, avoiding version-sensitive helpers.
