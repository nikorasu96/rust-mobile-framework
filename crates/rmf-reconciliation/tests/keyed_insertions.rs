//! Public contracts for deterministic single-child keyed insertion.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertySet, ValidatedTree,
};
use rmf_reconciliation::{Mutation, ReconcileError, ReconcileLimits, Reconciler, SurfaceSnapshot};

fn keyed_text(key: &str) -> DeclarativeNode {
    DeclarativeNode::new(
        ComponentKind::Text,
        Some(Key::new(String::from(key))),
        PropertySet::empty(),
        vec![],
    )
}

fn tree(keys: &[&str]) -> ValidatedTree {
    let children = keys.iter().map(|key| keyed_text(key)).collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid keyed fixture: {error}"))
}

fn unkeyed_tree(child_count: usize) -> ValidatedTree {
    let children = (0..child_count)
        .map(|_| {
            DeclarativeNode::new(
                ComponentKind::Text,
                None,
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid unkeyed fixture: {error}"))
}

fn reconciler(limit: u32) -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(limit)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    )
}

fn initial_snapshot(keys: &[&str]) -> SurfaceSnapshot {
    reconciler(20)
        .prepare(&SurfaceSnapshot::empty(), &tree(keys))
        .unwrap_or_else(|error| unreachable!("initial keyed fixture must prepare: {error}"))
        .into_snapshot()
}

fn child_ids(snapshot: &SurfaceSnapshot) -> Vec<u64> {
    snapshot
        .root()
        .map_or(&[][..], rmf_reconciliation::CommittedNode::children)
        .iter()
        .map(|child| child.node_id().get())
        .collect()
}

#[test]
fn inserts_one_keyed_child_and_preserves_sibling_identities() {
    let current = initial_snapshot(&["a", "c"]);
    assert_eq!(child_ids(&current), [2, 3]);

    let prepared = reconciler(20)
        .prepare(&current, &tree(&["a", "b", "c"]))
        .unwrap_or_else(|error| unreachable!("one keyed insertion must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [
            Mutation::Create { node_id, kind: ComponentKind::Text },
            Mutation::InsertChild { parent_id, child_id, index },
        ] if node_id.get() == 4
            && parent_id.get() == 1
            && *child_id == *node_id
            && index.get() == 1
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [2, 4, 3]);
}

#[test]
fn appends_one_keyed_child_deterministically() {
    let current = initial_snapshot(&["a", "b"]);
    let prepared = reconciler(20)
        .prepare(&current, &tree(&["a", "b", "c"]))
        .unwrap_or_else(|error| unreachable!("keyed append must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [Mutation::Create { node_id, .. }, Mutation::InsertChild { child_id, index, .. }]
            if *child_id == *node_id && index.get() == 2
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [2, 3, 4]);
}

#[test]
fn rejects_an_unkeyed_insertion_as_ambiguous() {
    let current = reconciler(20)
        .prepare(&SurfaceSnapshot::empty(), &unkeyed_tree(2))
        .unwrap_or_else(|error| unreachable!("initial unkeyed fixture must prepare: {error}"))
        .into_snapshot();

    assert_eq!(
        reconciler(20).prepare(&current, &unkeyed_tree(3)),
        Err(ReconcileError::StructuralChangeUnsupported)
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), [2, 3]);
}

#[test]
fn operation_limit_rejects_insertion_without_publishing_partial_state() {
    let current = initial_snapshot(&["a", "c"]);
    let before_ids = child_ids(&current);

    assert_eq!(
        reconciler(1).prepare(&current, &tree(&["a", "b", "c"])),
        Err(ReconcileError::OperationLimitExceeded { limit: 1 })
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}
