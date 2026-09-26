//! Contract tests for atomic mutation application and confirmed-snapshot remount.

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertyEntry, PropertyId, PropertySet,
    PropertyValue, ValidatedTree,
};
use rmf_reconciliation::{ReconcileLimits, Reconciler, SurfaceSnapshot};
use rmf_renderer_headless::{HeadlessApplyError, HeadlessMutationAdapter};
use rmf_runtime::commit::{ApplyFailure, BatchApplier, CommitCoordinator, SnapshotRemounter};

fn property_id(value: u32) -> PropertyId {
    PropertyId::new(value)
        .unwrap_or_else(|error| unreachable!("positive fixture property: {error}"))
}

fn text(key: &str, value: &str) -> DeclarativeNode {
    let properties = PropertySet::new(vec![PropertyEntry::new(
        property_id(1),
        PropertyValue::String(String::from(value)),
    )])
    .unwrap_or_else(|error| unreachable!("unique fixture property: {error}"));
    DeclarativeNode::new(
        ComponentKind::Text,
        Some(Key::new(String::from(key))),
        properties,
        vec![],
    )
}

fn view(key: &str) -> DeclarativeNode {
    DeclarativeNode::new(
        ComponentKind::View,
        Some(Key::new(String::from(key))),
        PropertySet::empty(),
        vec![],
    )
}

fn candidate(children: Vec<DeclarativeNode>) -> ValidatedTree {
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    ValidatedTree::new(root, CandidateLimits::default())
        .unwrap_or_else(|error| unreachable!("valid adapter fixture: {error}"))
}

fn reconciler() -> Reconciler {
    Reconciler::new(
        ReconcileLimits::new(100)
            .unwrap_or_else(|error| unreachable!("positive operation limit: {error}")),
    )
}

fn apply_candidate(
    coordinator: &mut CommitCoordinator<HeadlessMutationAdapter>,
    reconciler: &Reconciler,
    next: &ValidatedTree,
) {
    let prepared = reconciler
        .prepare(coordinator.confirmed_snapshot(), next)
        .unwrap_or_else(|error| unreachable!("fixture preparation succeeds: {error}"));
    coordinator
        .apply(prepared)
        .unwrap_or_else(|error| unreachable!("valid host batch applies: {error}"));
    assert!(
        coordinator
            .applier()
            .agrees_with(coordinator.confirmed_snapshot())
    );
}

#[test]
fn applies_every_v1_mutation_family_and_tracks_the_committed_snapshot() {
    let reconciler = reconciler();
    let mut coordinator = CommitCoordinator::new(HeadlessMutationAdapter::default());

    apply_candidate(
        &mut coordinator,
        &reconciler,
        &candidate(vec![text("a", "A"), text("b", "B")]),
    );
    assert_eq!(coordinator.applier().node_count(), 3);

    apply_candidate(
        &mut coordinator,
        &reconciler,
        &candidate(vec![text("b", "B2"), text("a", "A")]),
    );
    apply_candidate(
        &mut coordinator,
        &reconciler,
        &candidate(vec![text("b", "B2"), text("c", "C"), text("a", "A")]),
    );
    assert_eq!(coordinator.applier().node_count(), 4);

    apply_candidate(
        &mut coordinator,
        &reconciler,
        &candidate(vec![text("c", "C"), text("a", "A")]),
    );
    apply_candidate(
        &mut coordinator,
        &reconciler,
        &candidate(vec![text("c", "C"), view("a")]),
    );

    assert_eq!(coordinator.applier().node_count(), 3);
    assert_eq!(coordinator.applier().revision(), 5);
    assert_eq!(coordinator.applier().root_id(), Some(1));
}

#[test]
fn stale_batch_is_rejected_without_changing_host_state() {
    let reconciler = reconciler();
    let prepared = reconciler
        .prepare(&SurfaceSnapshot::empty(), &candidate(vec![text("a", "A")]))
        .unwrap_or_else(|error| unreachable!("fixture preparation succeeds: {error}"));
    let snapshot = prepared.clone().into_snapshot();
    let mut adapter = HeadlessMutationAdapter::default();

    assert_eq!(adapter.apply_batch(prepared.batch()), Ok(()));
    assert!(adapter.agrees_with(&snapshot));
    assert_eq!(
        adapter.apply_batch(prepared.batch()),
        Err(ApplyFailure::RejectedBeforeMutation(
            HeadlessApplyError::StaleRevision
        ))
    );
    assert!(adapter.agrees_with(&snapshot));
}

#[test]
fn remount_replaces_host_state_with_the_exact_confirmed_snapshot() {
    let reconciler = reconciler();
    let first = reconciler
        .prepare(
            &SurfaceSnapshot::empty(),
            &candidate(vec![text("a", "A"), text("b", "B")]),
        )
        .unwrap_or_else(|error| unreachable!("first fixture prepares: {error}"));
    let first_snapshot = first.clone().into_snapshot();
    let second = reconciler
        .prepare(
            &first_snapshot,
            &candidate(vec![text("b", "B2"), text("a", "A")]),
        )
        .unwrap_or_else(|error| unreachable!("second fixture prepares: {error}"));
    let second_snapshot = second.clone().into_snapshot();
    let mut adapter = HeadlessMutationAdapter::default();
    assert_eq!(adapter.apply_batch(first.batch()), Ok(()));
    assert_eq!(adapter.apply_batch(second.batch()), Ok(()));
    assert!(adapter.agrees_with(&second_snapshot));

    assert_eq!(adapter.remount_snapshot(&first_snapshot), Ok(()));
    assert!(adapter.agrees_with(&first_snapshot));
    assert_eq!(adapter.revision(), 1);
    assert_eq!(adapter.node_count(), 3);
}
