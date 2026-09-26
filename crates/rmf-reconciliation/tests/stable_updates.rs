//! Public contract coverage for property reconciliation on stable tree structure.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertyEntry, PropertyId, PropertySet,
    PropertyValue, ValidatedTree,
};
use rmf_reconciliation::{Mutation, ReconcileError, ReconcileLimits, Reconciler, SurfaceSnapshot};

fn property_id(value: u32) -> PropertyId {
    PropertyId::new(value).unwrap_or_else(|error| unreachable!("positive fixture ID: {error}"))
}

fn properties(entries: Vec<PropertyEntry>) -> PropertySet {
    PropertySet::new(entries)
        .unwrap_or_else(|error| unreachable!("unique fixture properties: {error}"))
}

fn tree(text_properties: PropertySet, key: &str) -> ValidatedTree {
    let text = DeclarativeNode::new(
        ComponentKind::Text,
        Some(Key::new(String::from(key))),
        text_properties,
        vec![],
    );
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), vec![text]);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid fixture candidate: {error}"))
}

fn unkeyed_tree(kind: ComponentKind, properties: PropertySet) -> ValidatedTree {
    let child = DeclarativeNode::new(kind, None, properties, vec![]);
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), vec![child]);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid unkeyed fixture candidate: {error}"))
}

fn reconciler() -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(20)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    )
}

fn initial_snapshot(properties: PropertySet, key: &str) -> SurfaceSnapshot {
    reconciler()
        .prepare(&SurfaceSnapshot::empty(), &tree(properties, key))
        .unwrap_or_else(|error| unreachable!("initial fixture must prepare: {error}"))
        .into_snapshot()
}

#[test]
fn updates_properties_while_preserving_keyed_identity() {
    let old = properties(vec![PropertyEntry::new(
        property_id(1),
        PropertyValue::String(String::from("Old")),
    )]);
    let current = initial_snapshot(old, "status");
    let previous_id = current
        .root()
        .and_then(|root| root.children().first())
        .map_or_else(
            || unreachable!("fixture child exists"),
            rmf_reconciliation::CommittedNode::node_id,
        );
    let new = properties(vec![PropertyEntry::new(
        property_id(1),
        PropertyValue::String(String::from("New")),
    )]);

    let prepared = reconciler()
        .prepare(&current, &tree(new, "status"))
        .unwrap_or_else(|error| unreachable!("stable update must prepare: {error}"));
    assert_eq!(prepared.batch().base_revision().get(), 1);
    assert_eq!(prepared.batch().target_revision().get(), 2);
    assert!(matches!(
        prepared.batch().operations(),
        [Mutation::UpdateProperties { node_id, set, remove }]
            if *node_id == previous_id && set.entries().len() == 1 && remove.is_empty()
    ));

    let next = prepared.into_snapshot();
    assert_eq!(
        next.root()
            .and_then(|root| root.children().first())
            .map(rmf_reconciliation::CommittedNode::node_id),
        Some(previous_id)
    );
}

#[test]
fn removes_properties_in_canonical_identity_order() {
    let old = properties(vec![
        PropertyEntry::new(
            property_id(1),
            PropertyValue::String(String::from("Visible")),
        ),
        PropertyEntry::new(property_id(2), PropertyValue::Bool(true)),
    ]);
    let current = initial_snapshot(old, "label");
    let new = properties(vec![PropertyEntry::new(
        property_id(2),
        PropertyValue::Bool(true),
    )]);

    let prepared = reconciler()
        .prepare(&current, &tree(new, "label"))
        .unwrap_or_else(|error| unreachable!("stable removal must prepare: {error}"));
    assert!(matches!(
        prepared.batch().operations(),
        [Mutation::UpdateProperties { set, remove, .. }]
            if set.entries().is_empty() && remove.as_ref() == [property_id(1)]
    ));
}

#[test]
fn rejects_unkeyed_replacement_atomically() {
    let current = reconciler()
        .prepare(
            &SurfaceSnapshot::empty(),
            &unkeyed_tree(ComponentKind::Text, PropertySet::empty()),
        )
        .unwrap_or_else(|error| unreachable!("initial unkeyed fixture must prepare: {error}"))
        .into_snapshot();

    assert_eq!(
        reconciler().prepare(
            &current,
            &unkeyed_tree(ComponentKind::View, PropertySet::empty()),
        ),
        Err(ReconcileError::StructuralChangeUnsupported)
    );
    assert_eq!(current.revision().get(), 1);
}
