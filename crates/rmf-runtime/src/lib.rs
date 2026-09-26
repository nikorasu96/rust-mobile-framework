#![doc = "Runtime orchestration and outbound ports."]

use std::error::Error;

use rmf_core::UiTree;
use surface::{
    CreateSurfaceError, StaleSurfaceHandle, SurfaceAccess, SurfaceHandle, SurfaceId,
    SurfaceRegistry,
};

pub mod surface;
pub mod commit;

/// Outbound port implemented by platform-specific renderers.
pub trait Renderer {
    /// Renderer-specific failure exposed without coupling the runtime to an adapter.
    type Error: Error + Send + Sync + 'static;

    /// Replaces the currently mounted frame with `tree`.
    ///
    /// # Errors
    ///
    /// Returns the adapter's typed error when rendering fails.
    fn render(&mut self, tree: &UiTree) -> Result<(), Self::Error>;
}

/// Coordinates framework use cases without knowing the platform adapter.
#[derive(Debug)]
pub struct Runtime<R> {
    renderer: R,
    surfaces: SurfaceRegistry,
}

impl<R> Runtime<R>
where
    R: Renderer,
{
    /// Creates a runtime with an injected renderer adapter.
    #[must_use]
    pub const fn new(renderer: R) -> Self {
        Self {
            renderer,
            surfaces: SurfaceRegistry::new(),
        }
    }

    /// Mounts a validated declarative tree.
    ///
    /// # Errors
    ///
    /// Returns the renderer adapter's typed error.
    pub fn mount(&mut self, tree: &UiTree) -> Result<(), R::Error> {
        self.renderer.render(tree)
    }

    /// Creates one runtime-owned surface generation.
    ///
    /// # Errors
    ///
    /// Returns a typed error when the logical slot is active or the generation allocator is
    /// exhausted.
    pub fn create_surface(
        &mut self,
        surface_id: SurfaceId,
    ) -> Result<SurfaceHandle, CreateSurfaceError> {
        self.surfaces.create(surface_id)
    }

    /// Invalidates an exact surface handle before platform cleanup begins.
    ///
    /// # Errors
    ///
    /// Returns [`StaleSurfaceHandle`] without mutation when the handle is no longer active.
    pub fn dispose_surface(&mut self, handle: SurfaceHandle) -> Result<(), StaleSurfaceHandle> {
        self.surfaces.dispose(handle)
    }

    /// Admits one callback only while its complete generational handle is live.
    ///
    /// The callback runs at most once and cannot retain the borrowed [`SurfaceAccess`] proof.
    ///
    /// # Errors
    ///
    /// Returns [`StaleSurfaceHandle`] without invoking `callback` when the handle is stale.
    pub fn dispatch_surface_callback<T>(
        &self,
        handle: SurfaceHandle,
        callback: impl FnOnce(SurfaceAccess<'_>) -> T,
    ) -> Result<T, StaleSurfaceHandle> {
        let access = self.surfaces.resolve(handle)?;
        Ok(callback(access))
    }

    /// Returns the number of live surfaces for diagnostics and capacity metrics.
    #[must_use]
    pub fn active_surface_count(&self) -> usize {
        self.surfaces.active_count()
    }

    /// Returns shared access to the adapter for diagnostics and composition roots.
    #[must_use]
    pub const fn renderer(&self) -> &R {
        &self.renderer
    }

    /// Consumes the runtime and returns its adapter.
    #[must_use]
    pub fn into_renderer(self) -> R {
        self.renderer
    }
}

#[cfg(test)]
mod tests {
    use std::convert::Infallible;

    use rmf_core::{Element, NodeId, UiNode, UiTree};

    use super::{Renderer, Runtime};

    #[derive(Default)]
    struct SpyRenderer {
        calls: usize,
    }

    impl Renderer for SpyRenderer {
        type Error = Infallible;

        fn render(&mut self, _tree: &UiTree) -> Result<(), Self::Error> {
            self.calls += 1;
            Ok(())
        }
    }

    #[test]
    fn mount_delegates_once_to_renderer_port() {
        let node_id = match NodeId::new(1) {
            Ok(id) => id,
            Err(error) => unreachable!("fixture id is valid: {error}"),
        };
        let tree = match UiTree::new(UiNode::new(node_id, Element::View, vec![])) {
            Ok(tree) => tree,
            Err(error) => unreachable!("fixture tree is valid: {error}"),
        };
        let mut runtime = Runtime::new(SpyRenderer::default());

        assert!(runtime.mount(&tree).is_ok());
        assert_eq!(runtime.renderer().calls, 1);
    }
}
