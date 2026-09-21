use std::error::Error;

use rmf_core::{Element, NodeId, UiNode, UiTree};
use rmf_renderer_headless::HeadlessRenderer;
use rmf_runtime::Runtime;

fn main() -> Result<(), Box<dyn Error>> {
    let tree = UiTree::new(UiNode::new(
        NodeId::new(1)?,
        Element::View,
        vec![UiNode::new(
            NodeId::new(2)?,
            Element::Text(String::from("Hello from Rust")),
            vec![],
        )],
    ))?;
    let mut runtime = Runtime::new(HeadlessRenderer::default());

    runtime.mount(&tree)?;
    if let Some(frame) = runtime.renderer().last_frame() {
        print!("{frame}");
    }

    Ok(())
}

