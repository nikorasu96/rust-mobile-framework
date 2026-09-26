//! Public contracts for deterministic single-child keyed removal.

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

fn tree(children: Vec<DeclarativeNode>) -> ValidatedTree {
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid removal fixture: {error}"))
}

fn keyed_text(key: &str) -> DeclarativeNode {
    keyed_node(ComponentKind::Text, key, vec![])
}

fn keyed_tree(keys: &[&str]) -> ValidatedTree {
    tree(keys.iter().map(|key| keyed_text(key)).collect())
}

fn unkeyed_tree(child_count: usize) -> ValidatedTree {
    let children = (0..child_count)
        .map(|_| DeclarativeNode::new(ComponentKind::Text, None, PropertySet::empty(), vec![]))
        .collect();
    tree(children)
}

fn reconciler(limit: u32) -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(limit)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    )
}

fn snapshot(candidate: &ValidatedTree) -> SurfaceSnapshot {
    reconciler(30)
        .prepare(&SurfaceSnapshot::empty(), candidate)
        .unwrap_or_else(|error| unreachable!("initial removal fixture must prepare: {error}"))
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
fn removes_one_keyed_child_and_preserves_sibling_identities() {
    let current = snapshot(&keyed_tree(&["a", "b", "c"]));
    assert_eq!(child_ids(&current), [2, 3, 4]);

    let prepared = reconciler(30)
        .prepare(&current, &keyed_tree(&["a", "c"]))
        .unwrap_or_else(|error| unreachable!("one keyed removal must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [
            Mutation::RemoveChild { parent_id, child_id, index },
            Mutation::Delete { node_id },
        ] if parent_id.get() == 1
            && child_id.get() == 3
            && index.get() == 1
            && *node_id == *child_id
    ));
    assert_eq!(child_ids(&prepared.into_snapshot()), [2, 4]);
}

#[test]
fn removes_a_subtree_in_detach_then_descendant_first_order() {
    let leaf = keyed_text("message");
    let panel = keyed_node(ComponentKind::View, "panel", vec![leaf]);
    let current = snapshot(&tree(vec![panel]));
    let prepared = reconciler(30)
        .prepare(&current, &tree(vec![]))
        .unwrap_or_else(|error| unreachable!("keyed subtree removal must prepare: {error}"));

    assert!(matches!(
        prepared.batch().operations(),
        [
            Mutation::RemoveChild { parent_id: root_id, child_id: panel_id, index: panel_index },
            Mutation::RemoveChild { parent_id: nested_parent, child_id: leaf_id, index: leaf_index },
            Mutation::Delete { node_id: deleted_leaf },
            Mutation::Delete { node_id: deleted_panel },
        ] if root_id.get() == 1
            && panel_id.get() == 2
            && panel_index.get() == 0
            && *nested_parent == *panel_id
            && leaf_id.get() == 3
            && leaf_index.get() == 0
            && *deleted_leaf == *leaf_id
            && *deleted_panel == *panel_id
    ));
    assert!(child_ids(&prepared.into_snapshot()).is_empty());
}

#[test]
fn rejects_an_unkeyed_removal_as_ambiguous() {
    let current = snapshot(&unkeyed_tree(3));

    assert_eq!(
        reconciler(30).prepare(&current, &unkeyed_tree(2)),
        Err(ReconcileError::StructuralChangeUnsupported)
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), [2, 3, 4]);
}

#[test]
fn operation_limit_rejects_subtree_removal_without_publishing_partial_state() {
    let leaf = keyed_text("message");
    let panel = keyed_node(ComponentKind::View, "panel", vec![leaf]);
    let current = snapshot(&tree(vec![panel]));
    let before_ids = child_ids(&current);

    assert_eq!(
        reconciler(1).prepare(&current, &tree(vec![])),
        Err(ReconcileError::OperationLimitExceeded { limit: 1 })
    );
    assert_eq!(current.revision().get(), 1);
    assert_eq!(child_ids(&current), before_ids);
}
