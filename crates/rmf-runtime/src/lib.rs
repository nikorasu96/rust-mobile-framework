#![doc = "Runtime orchestration and outbound ports."]

use std::error::Error;

use rmf_core::UiTree;

pub mod surface;

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
}

impl<R> Runtime<R>
where
    R: Renderer,
{
    /// Creates a runtime with an injected renderer adapter.
    #[must_use]
    pub const fn new(renderer: R) -> Self {
        Self { renderer }
    }

    /// Mounts a validated declarative tree.
    ///
    /// # Errors
    ///
    /// Returns the renderer adapter's typed error.
    pub fn mount(&mut self, tree: &UiTree) -> Result<(), R::Error> {
        self.renderer.render(tree)
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
