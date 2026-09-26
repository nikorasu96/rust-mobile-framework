#![doc = "Dependency-free release performance gate."]

use std::convert::Infallible;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::hint::black_box;
use std::time::{Duration, Instant};

use rmf_core::candidate::{
    CandidateLimits, ComponentKind, DeclarativeNode, Key, PropertySet, ValidatedTree,
};
use rmf_core::{Element, NodeId, UiNode, UiTree};
use rmf_reconciliation::{MutationBatch, ReconcileLimits, Reconciler, SurfaceSnapshot};
use rmf_renderer_headless::HeadlessRenderer;
use rmf_runtime::commit::{ApplyFailure, BatchApplier, CommitCoordinator};
use rmf_runtime::Runtime;

const NODE_COUNT: usize = 1_000;
const ITERATIONS: u32 = 100;
const VALIDATION_BUDGET: Duration = Duration::from_millis(1);
const MOUNT_BUDGET: Duration = Duration::from_millis(2);
const KEYED_MOVE_BUDGET: Duration = Duration::from_millis(5);
const KEYED_INSERTION_BUDGET: Duration = Duration::from_millis(5);
const KEYED_REMOVAL_BUDGET: Duration = Duration::from_millis(5);
const KEYED_REPLACEMENT_BUDGET: Duration = Duration::from_millis(5);
const COMMIT_PROMOTION_BUDGET: Duration = Duration::from_millis(1);
const FRAME_BYTES_BUDGET: usize = 2 * 1024 * 1024;

fn main() -> Result<(), Box<dyn Error>> {
    let root = build_linear_tree(NODE_COUNT)?;

    let validation_started = Instant::now();
    for _ in 0..ITERATIONS {
        let validated = UiTree::new(black_box(root.clone()))?;
        black_box(validated);
    }
    let validation_average = validation_started.elapsed() / ITERATIONS;

    let tree = UiTree::new(root)?;
    let mut runtime = Runtime::new(HeadlessRenderer::default());
    let mount_started = Instant::now();
    for _ in 0..ITERATIONS {
        runtime.mount(black_box(&tree))?;
    }
    let mount_average = mount_started.elapsed() / ITERATIONS;
    let frame_bytes = runtime.renderer().last_frame().map_or(0, str::len);

    let reconciler = Reconciler::new(ReconcileLimits::new(3_000)?);
    let initial_candidate = build_keyed_sibling_tree(NODE_COUNT, false)?;
    let snapshot = reconciler
        .prepare(&SurfaceSnapshot::empty(), &initial_candidate)?
        .into_snapshot();
    let moved_candidate = build_keyed_sibling_tree(NODE_COUNT, true)?;
    let keyed_move_started = Instant::now();
    for _ in 0..ITERATIONS {
        let prepared = reconciler.prepare(black_box(&snapshot), black_box(&moved_candidate))?;
        black_box(prepared);
    }
    let keyed_move_average = keyed_move_started.elapsed() / ITERATIONS;

    let keyed_insertion_average = measure_keyed_insertion(reconciler)?;
    let keyed_removal_average = measure_keyed_removal(reconciler)?;

    let keyed_replacement_average = measure_keyed_replacement(reconciler)?;
    let commit_promotion_average = measure_commit_promotion()?;

    println!("nodes={NODE_COUNT}");
    println!("iterations={ITERATIONS}");
    println!("validation_average_ns={}", validation_average.as_nanos());
    println!("mount_average_ns={}", mount_average.as_nanos());
    println!("keyed_move_average_ns={}", keyed_move_average.as_nanos());
    println!(
        "keyed_insertion_average_ns={}",
        keyed_insertion_average.as_nanos()
    );
    println!(
        "keyed_removal_average_ns={}",
        keyed_removal_average.as_nanos()
    );
    println!(
        "keyed_replacement_average_ns={}",
        keyed_replacement_average.as_nanos()
    );
    println!(
        "commit_promotion_average_ns={}",
        commit_promotion_average.as_nanos()
    );
    println!("frame_bytes={frame_bytes}");

    enforce_budget("validation average", validation_average, VALIDATION_BUDGET)?;
    enforce_budget("mount average", mount_average, MOUNT_BUDGET)?;
    enforce_budget("keyed move average", keyed_move_average, KEYED_MOVE_BUDGET)?;
    enforce_budget(
        "keyed insertion average",
        keyed_insertion_average,
        KEYED_INSERTION_BUDGET,
    )?;
    enforce_budget(
        "keyed removal average",
        keyed_removal_average,
        KEYED_REMOVAL_BUDGET,
    )?;
    enforce_budget(
        "keyed replacement average",
        keyed_replacement_average,
        KEYED_REPLACEMENT_BUDGET,
    )?;
    enforce_budget(
        "commit promotion average",
        commit_promotion_average,
        COMMIT_PROMOTION_BUDGET,
    )?;
    if frame_bytes > FRAME_BYTES_BUDGET {
        return Err(Box::new(BudgetExceeded::Bytes {
            actual: frame_bytes,
            budget: FRAME_BYTES_BUDGET,
        }));
    }

    println!("budget_status=passed");
    Ok(())
}

#[derive(Debug, Default)]
struct NoopBatchApplier;

impl BatchApplier for NoopBatchApplier {
    type Error = Infallible;

    fn apply_batch(
        &mut self,
        _batch: &MutationBatch,
    ) -> Result<(), ApplyFailure<Self::Error>> {
        Ok(())
    }
}

fn measure_commit_promotion() -> Result<Duration, Box<dyn Error>> {
    let reconciler = Reconciler::new(ReconcileLimits::new(3_000)?);
    let candidate = build_keyed_sibling_tree(NODE_COUNT, false)?;
    let mut coordinator = CommitCoordinator::new(NoopBatchApplier);
    let initial = reconciler.prepare(coordinator.confirmed_snapshot(), &candidate)?;
    coordinator.apply(initial)?;

    let started = Instant::now();
    for _ in 0..ITERATIONS {
        let prepared = reconciler.prepare(coordinator.confirmed_snapshot(), &candidate)?;
        coordinator.apply(prepared)?;
    }
    Ok(started.elapsed() / ITERATIONS)
}

fn measure_keyed_insertion(reconciler: Reconciler) -> Result<Duration, Box<dyn Error>> {
    let base = build_keyed_insertion_tree(NODE_COUNT, false)?;
    let snapshot = reconciler
        .prepare(&SurfaceSnapshot::empty(), &base)?
        .into_snapshot();
    let candidate = build_keyed_insertion_tree(NODE_COUNT, true)?;
    let started = Instant::now();
    for _ in 0..ITERATIONS {
        let prepared = reconciler.prepare(black_box(&snapshot), black_box(&candidate))?;
        black_box(prepared);
    }
    Ok(started.elapsed() / ITERATIONS)
}

fn measure_keyed_removal(reconciler: Reconciler) -> Result<Duration, Box<dyn Error>> {
    let base = build_keyed_removal_tree(NODE_COUNT, false)?;
    let snapshot = reconciler
        .prepare(&SurfaceSnapshot::empty(), &base)?
        .into_snapshot();
    let candidate = build_keyed_removal_tree(NODE_COUNT, true)?;
    let started = Instant::now();
    for _ in 0..ITERATIONS {
        let prepared = reconciler.prepare(black_box(&snapshot), black_box(&candidate))?;
        black_box(prepared);
    }
    Ok(started.elapsed() / ITERATIONS)
}

fn measure_keyed_replacement(reconciler: Reconciler) -> Result<Duration, Box<dyn Error>> {
    let base = build_keyed_replacement_tree(NODE_COUNT, false)?;
    let snapshot = reconciler
        .prepare(&SurfaceSnapshot::empty(), &base)?
        .into_snapshot();
    let candidate = build_keyed_replacement_tree(NODE_COUNT, true)?;
    let started = Instant::now();
    for _ in 0..ITERATIONS {
        let prepared = reconciler.prepare(black_box(&snapshot), black_box(&candidate))?;
        black_box(prepared);
    }
    Ok(started.elapsed() / ITERATIONS)
}

fn build_keyed_replacement_tree(
    child_count: usize,
    replace_middle_child: bool,
) -> Result<ValidatedTree, Box<dyn Error>> {
    let replacement_index = child_count / 2;
    let children = (0..child_count)
        .map(|index| {
            let kind = if replace_middle_child && index == replacement_index {
                ComponentKind::View
            } else {
                ComponentKind::Text
            };
            DeclarativeNode::new(
                kind,
                Some(Key::new(index.to_string())),
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    Ok(ValidatedTree::new(root, CandidateLimits::default())?)
}

fn build_keyed_removal_tree(
    initial_child_count: usize,
    remove_middle_child: bool,
) -> Result<ValidatedTree, Box<dyn Error>> {
    let mut keys: Vec<usize> = (0..initial_child_count).collect();
    if remove_middle_child && !keys.is_empty() {
        keys.remove(initial_child_count / 2);
    }
    let children = keys
        .into_iter()
        .map(|index| {
            DeclarativeNode::new(
                ComponentKind::Text,
                Some(Key::new(index.to_string())),
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    Ok(ValidatedTree::new(root, CandidateLimits::default())?)
}

fn build_keyed_insertion_tree(
    final_child_count: usize,
    include_inserted_child: bool,
) -> Result<ValidatedTree, Box<dyn Error>> {
    let existing_count = final_child_count.saturating_sub(1);
    let mut keys: Vec<usize> = (0..existing_count).collect();
    if include_inserted_child {
        keys.insert(final_child_count / 2, existing_count);
    }
    let children = keys
        .into_iter()
        .map(|index| {
            DeclarativeNode::new(
                ComponentKind::Text,
                Some(Key::new(index.to_string())),
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    Ok(ValidatedTree::new(root, CandidateLimits::default())?)
}

fn build_keyed_sibling_tree(
    child_count: usize,
    move_last_to_front: bool,
) -> Result<ValidatedTree, Box<dyn Error>> {
    let mut keys: Vec<usize> = (0..child_count).collect();
    if move_last_to_front {
        if let Some(last) = keys.pop() {
            keys.insert(0, last);
        }
    }
    let children = keys
        .into_iter()
        .map(|index| {
            DeclarativeNode::new(
                ComponentKind::Text,
                Some(Key::new(index.to_string())),
                PropertySet::empty(),
                vec![],
            )
        })
        .collect();
    let root = DeclarativeNode::new(ComponentKind::View, None, PropertySet::empty(), children);
    Ok(ValidatedTree::new(root, CandidateLimits::default())?)
}

fn build_linear_tree(node_count: usize) -> Result<UiNode, Box<dyn Error>> {
    let leaf_id = NodeId::new(u64::try_from(node_count)?)?;
    let mut current = UiNode::new(leaf_id, Element::Text(String::from("leaf")), vec![]);

    for raw_id in (1..node_count).rev() {
        let id = NodeId::new(u64::try_from(raw_id)?)?;
        current = UiNode::new(id, Element::View, vec![current]);
    }

    Ok(current)
}

fn enforce_budget(
    name: &'static str,
    actual: Duration,
    budget: Duration,
) -> Result<(), BudgetExceeded> {
    if actual > budget {
        Err(BudgetExceeded::Duration {
            name,
            actual,
            budget,
        })
    } else {
        Ok(())
    }
}

#[derive(Debug)]
enum BudgetExceeded {
    Duration {
        name: &'static str,
        actual: Duration,
        budget: Duration,
    },
    Bytes {
        actual: usize,
        budget: usize,
    },
}

impl Display for BudgetExceeded {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::Duration {
                name,
                actual,
                budget,
            } => write!(formatter, "{name} exceeded budget: {actual:?} > {budget:?}"),
            Self::Bytes { actual, budget } => {
                write!(
                    formatter,
                    "frame exceeded budget: {actual} bytes > {budget} bytes"
                )
            }
        }
    }
}

impl Error for BudgetExceeded {}
