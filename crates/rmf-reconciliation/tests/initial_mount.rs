//! Public contract coverage for deterministic initial-mount reconciliation.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertyEntry, PropertyId, PropertySet,
    PropertyValue, ValidatedTree,
};
use rmf_reconciliation::{Mutation, ReconcileError, ReconcileLimits, Reconciler, SurfaceSnapshot};

fn property_id(value: u32) -> PropertyId {
    PropertyId::new(value).unwrap_or_else(|error| unreachable!("positive fixture ID: {error}"))
}

fn candidate() -> ValidatedTree {
    let properties = PropertySet::new(vec![PropertyEntry::new(
        property_id(1),
        PropertyValue::String(String::from("Hello")),
    )])
    .unwrap_or_else(|error| unreachable!("unique fixture property: {error}"));
    let text = DeclarativeNode::new(
        ComponentKind::Text,
        Some(Key::new(String::from("greeting"))),
        properties,
        vec![],
    );
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), vec![text]);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid fixture candidate: {error}"))
}

#[test]
fn prepares_the_initial_mount_fixture_in_topological_order() {
    let current = SurfaceSnapshot::empty();
    let reconciler = Reconciler::new(
        ReconcileLimits::new(10)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    );
    let prepared = reconciler
        .prepare(&current, &candidate())
        .unwrap_or_else(|error| unreachable!("initial mount must prepare: {error}"));

    let operations = prepared.batch().operations();
    assert_eq!(prepared.batch().base_revision().get(), 0);
    assert_eq!(prepared.batch().target_revision().get(), 1);
    assert_eq!(operations.len(), 4);
    assert!(matches!(
        operations[0],
        Mutation::Create { node_id, kind: ComponentKind::View } if node_id.get() == 1
    ));
    assert!(matches!(
        operations[1],
        Mutation::Create { node_id, kind: ComponentKind::Text } if node_id.get() == 2
    ));
    assert!(matches!(
        &operations[2],
        Mutation::UpdateProperties { node_id, set, remove }
            if node_id.get() == 2 && set.entries().len() == 1 && remove.is_empty()
    ));
    assert!(matches!(
        operations[3],
        Mutation::InsertChild { parent_id, child_id, index }
            if parent_id.get() == 1 && child_id.get() == 2 && index.get() == 0
    ));

    let snapshot = prepared.into_snapshot();
    let root = snapshot
        .root()
        .unwrap_or_else(|| unreachable!("root exists"));
    assert_eq!(snapshot.revision().get(), 1);
    assert_eq!(root.node_id().get(), 1);
    assert_eq!(root.children()[0].node_id().get(), 2);
    assert_eq!(root.children()[0].key().map(Key::as_str), Some("greeting"));
}

#[test]
fn operation_limit_rejects_the_whole_preparation_without_changing_current() {
    let current = SurfaceSnapshot::empty();
    let reconciler = Reconciler::new(
        ReconcileLimits::new(3)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    );

    assert_eq!(
        reconciler.prepare(&current, &candidate()),
        Err(ReconcileError::OperationLimitExceeded { limit: 3 })
    );
    assert_eq!(current.revision().get(), 0);
    assert!(current.root().is_none());
}

#[test]
fn refuses_to_treat_a_committed_snapshot_as_an_initial_mount() {
    let reconciler = Reconciler::new(
        ReconcileLimits::new(10)
            .unwrap_or_else(|error| unreachable!("positive fixture limit: {error}")),
    );
    let first = reconciler
        .prepare(&SurfaceSnapshot::empty(), &candidate())
        .unwrap_or_else(|error| unreachable!("initial mount must prepare: {error}"))
        .into_snapshot();

    assert_eq!(
        reconciler.prepare(&first, &candidate()),
        Err(ReconcileError::IncrementalReconciliationUnavailable)
    );
}

#[test]
fn immutable_public_values_are_send_and_sync() {
    const fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<SurfaceSnapshot>();
    assert_send_sync::<rmf_reconciliation::PreparedCommit>();
    assert_send_sync::<rmf_reconciliation::MutationBatch>();
}
