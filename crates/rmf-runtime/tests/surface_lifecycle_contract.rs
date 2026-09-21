//! Rust integration evidence for the reviewed surface-lifecycle contract.

use std::cell::Cell;
use std::convert::Infallible;

use rmf_core::UiTree;
use rmf_runtime::surface::{CreateSurfaceError, SurfaceId};
use rmf_runtime::{Renderer, Runtime};

#[derive(Debug, Default)]
struct NoopRenderer;

impl Renderer for NoopRenderer {
    type Error = Infallible;

    fn render(&mut self, _tree: &UiTree) -> Result<(), Self::Error> {
        Ok(())
    }
}

fn surface_id(value: u64) -> SurfaceId {
    match SurfaceId::new(value) {
        Ok(surface_id) => surface_id,
        Err(error) => unreachable!("contract fixture uses a positive surface ID: {error}"),
    }
}

#[test]
fn create_callback_dispose_contract_runs_through_runtime() {
    // Translation of contracts/surface-lifecycle/v1/01-create-callback-dispose.json.
    let mut runtime = Runtime::new(NoopRenderer);
    let callback_count = Cell::new(0);

    let handle = match runtime.create_surface(surface_id(7)) {
        Ok(handle) => handle,
        Err(error) => unreachable!("empty runtime accepts the fixture surface: {error}"),
    };
    let admitted = runtime.dispatch_surface_callback(handle, |access| {
        callback_count.set(callback_count.get() + 1);
        access.handle()
    });

    assert_eq!(admitted, Ok(handle));
    assert_eq!(callback_count.get(), 1);
    assert_eq!(runtime.dispose_surface(handle), Ok(()));
    assert_eq!(runtime.active_surface_count(), 0);
}

#[test]
fn duplicate_and_stale_callbacks_are_rejected_before_user_code() {
    // Combines the reviewed duplicate and recreate/stale-callback boundary cases.
    let mut runtime = Runtime::new(NoopRenderer);
    let first = match runtime.create_surface(surface_id(7)) {
        Ok(handle) => handle,
        Err(error) => unreachable!("empty runtime accepts the fixture surface: {error}"),
    };
    assert_eq!(
        runtime.create_surface(surface_id(7)),
        Err(CreateSurfaceError::AlreadyActive(surface_id(7)))
    );
    assert_eq!(runtime.dispose_surface(first), Ok(()));
    let replacement = match runtime.create_surface(surface_id(7)) {
        Ok(handle) => handle,
        Err(error) => unreachable!("disposed slot accepts a replacement: {error}"),
    };
    let callback_ran = Cell::new(false);

    assert!(
        runtime
            .dispatch_surface_callback(first, |_| callback_ran.set(true))
            .is_err()
    );
    assert!(!callback_ran.get());
    assert_eq!(
        runtime.dispatch_surface_callback(replacement, |access| access.handle()),
        Ok(replacement)
    );
    assert_eq!(replacement.generation().get(), 2);
}
