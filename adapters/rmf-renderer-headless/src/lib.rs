#![doc = "Deterministic headless renderer for tests, tooling, and benchmarks."]

use std::convert::Infallible;

use rmf_core::{Element, UiNode, UiTree};
use rmf_runtime::Renderer;

/// Renderer that serializes a tree into a stable, human-readable frame.
#[derive(Debug, Default)]
pub struct HeadlessRenderer {
    last_frame: Option<String>,
}

impl HeadlessRenderer {
    /// Returns the most recently rendered frame.
    #[must_use]
    pub fn last_frame(&self) -> Option<&str> {
        self.last_frame.as_deref()
    }
}

impl Renderer for HeadlessRenderer {
    type Error = Infallible;

    fn render(&mut self, tree: &UiTree) -> Result<(), Self::Error> {
        let mut frame = String::new();
        write_node(tree.root(), 0, &mut frame);
        self.last_frame = Some(frame);
        Ok(())
    }
}

fn write_node(node: &UiNode, depth: usize, output: &mut String) {
    output.push_str(&"  ".repeat(depth));
    match node.element() {
        Element::View => output.push_str("View"),
        Element::Text(value) => {
            output.push_str("Text(");
            output.push_str(value);
            output.push(')');
        }
    }
    output.push('#');
    output.push_str(&node.id().get().to_string());
    output.push('\n');

    for child in node.children() {
        write_node(child, depth + 1, output);
    }
}

#[cfg(test)]
mod tests {
    use rmf_core::{Element, NodeId, UiNode, UiTree};
    use rmf_runtime::{Renderer, Runtime};

    use super::HeadlessRenderer;

    fn id(value: u64) -> NodeId {
        match NodeId::new(value) {
            Ok(id) => id,
            Err(error) => unreachable!("fixture id is valid: {error}"),
        }
    }

    #[test]
    fn renders_a_stable_preorder_frame() {
        let tree = match UiTree::new(UiNode::new(
            id(1),
            Element::View,
            vec![UiNode::new(
                id(2),
                Element::Text(String::from("Hello")),
                vec![],
            )],
        )) {
            Ok(tree) => tree,
            Err(error) => unreachable!("fixture tree is valid: {error}"),
        };
        let mut runtime = Runtime::new(HeadlessRenderer::default());

        assert!(runtime.mount(&tree).is_ok());
        assert_eq!(
            runtime.renderer().last_frame(),
            Some("View#1\n  Text(Hello)#2\n")
        );
    }

    #[test]
    fn a_second_mount_replaces_the_previous_frame() {
        let first = match UiTree::new(UiNode::new(id(1), Element::View, vec![])) {
            Ok(tree) => tree,
            Err(error) => unreachable!("fixture tree is valid: {error}"),
        };
        let second = match UiTree::new(UiNode::new(
            id(2),
            Element::Text(String::from("Next")),
            vec![],
        )) {
            Ok(tree) => tree,
            Err(error) => unreachable!("fixture tree is valid: {error}"),
        };
        let mut renderer = HeadlessRenderer::default();

        assert!(renderer.render(&first).is_ok());
        assert!(renderer.render(&second).is_ok());
        assert_eq!(renderer.last_frame(), Some("Text(Next)#2\n"));
    }
}
