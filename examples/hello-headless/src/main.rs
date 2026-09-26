#![doc = "Executable headless composition-root example."]

use std::error::Error;
use std::fmt::{self, Display, Formatter};

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, PropertyEntry, PropertyId, PropertySet,
    PropertyValue, ValidatedTree,
};
use rmf_reconciliation::{ReconcileLimits, Reconciler};
use rmf_renderer_headless::HeadlessMutationAdapter;
use rmf_runtime::commit::CommitCoordinator;

#[derive(Debug)]
struct HostSnapshotMismatch;

impl Display for HostSnapshotMismatch {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("headless host does not match the confirmed snapshot")
    }
}

impl Error for HostSnapshotMismatch {}

fn main() -> Result<(), Box<dyn Error>> {
    let text = DeclarativeNode::new(
        ComponentKind::Text,
        None,
        PropertySet::new(vec![PropertyEntry::new(
            PropertyId::new(1)?,
            PropertyValue::String(String::from("Hello from Rust")),
        )])?,
        vec![],
    );
    let candidate = ValidatedTree::new(
        DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), vec![text]),
        CandidateLimits::default(),
    )?;
    let reconciler = Reconciler::new(ReconcileLimits::new(16)?);
    let mut coordinator = CommitCoordinator::new(HeadlessMutationAdapter::default());
    let prepared = reconciler.prepare(coordinator.confirmed_snapshot(), &candidate)?;

    coordinator.apply(prepared)?;
    if !coordinator
        .applier()
        .agrees_with(coordinator.confirmed_snapshot())
    {
        return Err(Box::new(HostSnapshotMismatch));
    }
    let adapter = coordinator.applier();
    println!(
        "revision={} root={} nodes={}",
        adapter.revision(),
        adapter.root_id().ok_or(HostSnapshotMismatch)?,
        adapter.node_count()
    );

    Ok(())
}
