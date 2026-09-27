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
    reconciler_with_limit(20)
}

fn reconciler_with_limit(limit: u32) -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(limit)
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
fn reorders_multiple_keyed_children_deterministically() {
    let current = initial_snapshot(&["a", "b", "c", "d"]);
    let prepared = reconciler()
        .prepare(&current, &tree(&["c", "d", "a", "b"]))
        .unwrap_or_else(|error| unreachable!("general keyed reorder must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [
            Mutation::MoveChild {
                child_id: first_child,
                from: first_from,
                to: first_to,
                ..
            },
            Mutation::MoveChild {
                child_id: second_child,
                from: second_from,
                to: second_to,
                ..
            }
        ] if first_child.get() == 4
            && first_from.get() == 2
            && first_to.get() == 0
            && second_child.get() == 5
            && second_from.get() == 3
            && second_to.get() == 1
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [4, 5, 2, 3]);
}

#[test]
fn reverse_order_uses_a_stable_bounded_move_sequence() {
    let current = initial_snapshot(&["a", "b", "c", "d"]);
    let candidate = tree(&["d", "c", "b", "a"]);
    let first = reconciler()
        .prepare(&current, &candidate)
        .unwrap_or_else(|error| unreachable!("reverse keyed reorder must prepare: {error}"));
    let second = reconciler()
        .prepare(&current, &candidate)
        .unwrap_or_else(|error| unreachable!("repeated keyed reorder must prepare: {error}"));

    assert_eq!(first.batch().operations(), second.batch().operations());
    assert_eq!(first.batch().operations().len(), 3);
    assert_eq!(child_ids(&first.into_snapshot()), [5, 4, 3, 2]);
}

#[test]
fn operation_limit_rejects_general_reorder_without_publishing_partial_state() {
    let current = initial_snapshot(&["a", "b", "c", "d"]);
    let before_ids = child_ids(&current);

    assert_eq!(
        reconciler_with_limit(1).prepare(&current, &tree(&["d", "c", "b", "a"])),
        Err(ReconcileError::OperationLimitExceeded { limit: 1 })
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}
