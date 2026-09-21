use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::hint::black_box;
use std::time::{Duration, Instant};

use rmf_core::{Element, NodeId, UiNode, UiTree};
use rmf_renderer_headless::HeadlessRenderer;
use rmf_runtime::Runtime;

const NODE_COUNT: usize = 1_000;
const ITERATIONS: u32 = 100;
const VALIDATION_BUDGET: Duration = Duration::from_millis(1);
const MOUNT_BUDGET: Duration = Duration::from_millis(2);
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

    println!("nodes={NODE_COUNT}");
    println!("iterations={ITERATIONS}");
    println!("validation_average_ns={}", validation_average.as_nanos());
    println!("mount_average_ns={}", mount_average.as_nanos());
    println!("frame_bytes={frame_bytes}");

    enforce_budget("validation average", validation_average, VALIDATION_BUDGET)?;
    enforce_budget("mount average", mount_average, MOUNT_BUDGET)?;
    if frame_bytes > FRAME_BYTES_BUDGET {
        return Err(Box::new(BudgetExceeded::Bytes {
            actual: frame_bytes,
            budget: FRAME_BYTES_BUDGET,
        }));
    }

    println!("budget_status=passed");
    Ok(())
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
