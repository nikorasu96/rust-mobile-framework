//! Public contracts for deterministic single-child keyed replacement.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertySet, ValidatedTree,
};
use rmf_reconciliation::{Mutation, ReconcileError, ReconcileLimits, Reconciler, SurfaceSnapshot};

fn keyed_node(kind: ComponentKind, key: &str, children: Vec<DeclarativeNode>) -> DeclarativeNode {
    DeclarativeNode::new(
        kind,
        Some(Key::new(String::from(key))),
        PropertySet::empty(),
        children,
    )
}

fn keyed_text(key: &str) -> DeclarativeNode {
    keyed_node(ComponentKind::Text, key, vec![])
}

fn tree(children: Vec<DeclarativeNode>) -> ValidatedTree {
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid replacement fixture: {error}"))
}

fn reconciler(limit: u32) -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(limit)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    )
}

fn snapshot(candidate: &ValidatedTree) -> SurfaceSnapshot {
    reconciler(40)
        .prepare(&SurfaceSnapshot::empty(), candidate)
        .unwrap_or_else(|error| unreachable!("initial replacement fixture must prepare: {error}"))
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
fn replaces_a_keyed_child_when_its_kind_changes() {
    let current = snapshot(&tree(vec![keyed_text("content")]));
    let candidate = tree(vec![keyed_node(ComponentKind::View, "content", vec![])]);
    let prepared = reconciler(40)
        .prepare(&current, &candidate)
        .unwrap_or_else(|error| unreachable!("keyed kind replacement must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [
            Mutation::RemoveChild { parent_id, child_id: old_id, index: remove_index },
            Mutation::Delete { node_id: deleted_id },
            Mutation::Create { node_id: new_id, kind: ComponentKind::View },
            Mutation::InsertChild { child_id: inserted_id, index: insert_index, .. },
        ] if parent_id.get() == 1
            && old_id.get() == 2
            && remove_index.get() == 0
            && *deleted_id == *old_id
            && new_id.get() == 3
            && *inserted_id == *new_id
            && insert_index.get() == 0
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [3]);
}

#[test]
fn replaces_one_changed_key_without_changing_sibling_identities() {
    let current = snapshot(&tree(vec![
        keyed_text("a"),
        keyed_text("b"),
        keyed_text("c"),
    ]));
    let candidate = tree(vec![keyed_text("a"), keyed_text("x"), keyed_text("c")]);
    let prepared = reconciler(40)
        .prepare(&current, &candidate)
        .unwrap_or_else(|error| unreachable!("keyed identity replacement must prepare: {error}"));

    assert_eq!(child_ids(&current), [2, 3, 4]);
    assert_eq!(child_ids(&prepared.into_snapshot()), [2, 5, 4]);
}

#[test]
fn replaces_nested_subtrees_in_delete_then_create_order() {
    let old_leaf = keyed_text("old-leaf");
    let old_panel = keyed_node(ComponentKind::View, "panel", vec![old_leaf]);
    let current = snapshot(&tree(vec![old_panel]));
    let new_leaf = keyed_text("new-leaf");
    let candidate = tree(vec![keyed_node(
        ComponentKind::View,
        "replacement-panel",
        vec![new_leaf],
    )]);
    let prepared = reconciler(40)
        .prepare(&current, &candidate)
        .unwrap_or_else(|error| unreachable!("nested keyed replacement must prepare: {error}"));

    let operations = prepared.batch().operations();
    assert_eq!(operations.len(), 8);
    assert!(matches!(operations[0], Mutation::RemoveChild { child_id, .. } if child_id.get() == 2));
    assert!(matches!(operations[1], Mutation::RemoveChild { child_id, .. } if child_id.get() == 3));
    assert!(matches!(operations[2], Mutation::Delete { node_id } if node_id.get() == 3));
    assert!(matches!(operations[3], Mutation::Delete { node_id } if node_id.get() == 2));
    assert!(matches!(operations[4], Mutation::Create { node_id, .. } if node_id.get() == 4));
    assert!(matches!(operations[5], Mutation::Create { node_id, .. } if node_id.get() == 5));
    assert!(
        matches!(operations[6], Mutation::InsertChild { parent_id, child_id, .. }
        if parent_id.get() == 4 && child_id.get() == 5)
    );
    assert!(
        matches!(operations[7], Mutation::InsertChild { parent_id, child_id, .. }
        if parent_id.get() == 1 && child_id.get() == 4)
    );
}

#[test]
fn rejects_multiple_replacements_without_publishing_partial_state() {
    let current = snapshot(&tree(vec![keyed_text("a"), keyed_text("b")]));
    let before_ids = child_ids(&current);
    let candidate = tree(vec![keyed_text("x"), keyed_text("y")]);

    assert_eq!(
        reconciler(40).prepare(&current, &candidate),
        Err(ReconcileError::StructuralChangeUnsupported)
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}

#[test]
fn operation_limit_rejects_replacement_without_publishing_partial_state() {
    let current = snapshot(&tree(vec![keyed_text("content")]));
    let before_ids = child_ids(&current);
    let candidate = tree(vec![keyed_node(ComponentKind::View, "content", vec![])]);

    assert_eq!(
        reconciler(3).prepare(&current, &candidate),
        Err(ReconcileError::OperationLimitExceeded { limit: 3 })
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}
