//! Public contracts for bounded linear-time keyed child movement.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertySet, ValidatedTree,
};
use rmf_reconciliation::{Mutation, ReconcileError, ReconcileLimits, Reconciler, SurfaceSnapshot};

fn tree(keys: &[&str]) -> ValidatedTree {
    let children = keys
        .iter()
        .map(|key| {
            DeclarativeNode::new(
                ComponentKind::Text,
                Some(Key::new(String::from(*key))),
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid keyed fixture: {error}"))
}

fn reconciler() -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(20)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    )
}

fn initial_snapshot(keys: &[&str]) -> SurfaceSnapshot {
    reconciler()
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
fn moves_one_keyed_child_earlier_and_preserves_all_identities() {
    let current = initial_snapshot(&["a", "b", "c"]);
    assert_eq!(child_ids(&current), [2, 3, 4]);

    let prepared = reconciler()
        .prepare(&current, &tree(&["c", "a", "b"]))
        .unwrap_or_else(|error| unreachable!("one keyed move must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [Mutation::MoveChild {
            parent_id,
            child_id,
            from,
            to,
        }] if parent_id.get() == 1
            && child_id.get() == 4
            && from.get() == 2
            && to.get() == 0
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [4, 2, 3]);
}

#[test]
fn moves_one_keyed_child_later_deterministically() {
    let current = initial_snapshot(&["a", "b", "c"]);
    let prepared = reconciler()
        .prepare(&current, &tree(&["b", "c", "a"]))
        .unwrap_or_else(|error| unreachable!("one keyed move must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [Mutation::MoveChild { child_id, from, to, .. }]
            if child_id.get() == 2 && from.get() == 0 && to.get() == 2
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [3, 4, 2]);
}

#[test]
fn rejects_multiple_keyed_moves_without_publishing_partial_state() {
    let current = initial_snapshot(&["a", "b", "c", "d"]);
    let before_ids = child_ids(&current);

    assert_eq!(
        reconciler().prepare(&current, &tree(&["c", "d", "a", "b"])),
        Err(ReconcileError::StructuralChangeUnsupported)
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}
