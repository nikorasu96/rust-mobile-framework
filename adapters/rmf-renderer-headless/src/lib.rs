#![doc = "Deterministic headless mutation adapter for tests, tooling, and benchmarks."]

mod mutation;

pub use mutation::{HeadlessApplyError, HeadlessHostMetrics, HeadlessMutationAdapter};
