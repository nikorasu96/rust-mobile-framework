#![doc = "Platform-independent UI model and invariants."]

use std::collections::HashSet;
use std::error::Error;
use std::fmt::{self, Display, Formatter};

/// Stable identity of a node within a UI tree.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct NodeId(u64);

impl NodeId {
    /// Creates a non-zero node identifier.
    ///
    /// # Errors
    ///
    /// Returns [`NodeIdError`] when `value` is zero.
    pub const fn new(value: u64) -> Result<Self, NodeIdError> {
        if value == 0 {
            Err(NodeIdError)
        } else {
            Ok(Self(value))
        }
    }

    /// Returns the primitive representation.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// Error returned when constructing an invalid node identifier.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NodeIdError;

impl Display for NodeIdError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("a node identifier must be non-zero")
    }
}

impl Error for NodeIdError {}

/// A minimal set of semantic elements used to validate the first runtime slice.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Element {
    /// A generic layout container.
    View,
    /// A semantic text leaf.
    Text(String),
}

/// Declarative UI node owned by the platform-independent core.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UiNode {
    id: NodeId,
    element: Element,
    children: Vec<Self>,
}

impl UiNode {
    /// Creates a node. Tree-wide invariants are checked by [`UiTree::new`].
    #[must_use]
    pub fn new(id: NodeId, element: Element, children: Vec<Self>) -> Self {
        Self {
            id,
            element,
            children,
        }
    }

    /// Returns this node's stable identity.
    #[must_use]
    pub const fn id(&self) -> NodeId {
        self.id
    }

    /// Returns the semantic element.
    #[must_use]
    pub const fn element(&self) -> &Element {
        &self.element
    }

    /// Returns child nodes in declaration order.
    #[must_use]
    pub fn children(&self) -> &[Self] {
        &self.children
    }
}
/// A declarative tree that satisfies all core structural invariants.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UiTree {
    root: UiNode,
}

impl UiTree {
    /// Validates and creates a UI tree.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] for duplicate identities or children under text nodes.
    pub fn new(root: UiNode) -> Result<Self, TreeError> {
        let mut identities = HashSet::new();
        validate_node(&root, &mut identities)?;
        Ok(Self { root })
    }

    /// Returns the root node.
    #[must_use]
    pub const fn root(&self) -> &UiNode {
        &self.root
    }
}

fn validate_node(node: &UiNode, identities: &mut HashSet<NodeId>) -> Result<(), TreeError> {
    if !identities.insert(node.id) {
        return Err(TreeError::DuplicateNodeId(node.id));
    }

    if matches!(node.element, Element::Text(_)) && !node.children.is_empty() {
        return Err(TreeError::TextHasChildren(node.id));
    }

    for child in &node.children {
        validate_node(child, identities)?;
    }

    Ok(())
}

/// Structural validation failure for a declarative UI tree.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TreeError {
    /// A node identity appeared more than once.
    DuplicateNodeId(NodeId),
    /// A text leaf incorrectly contained children.
    TextHasChildren(NodeId),
}

impl Display for TreeError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::DuplicateNodeId(id) => write!(formatter, "duplicate node id: {}", id.get()),
            Self::TextHasChildren(id) => {
                write!(formatter, "text node {} cannot contain children", id.get())
            }
        }
    }
}

impl Error for TreeError {}

#[cfg(test)]
mod tests {
    use super::{Element, NodeId, TreeError, UiNode, UiTree};

    fn id(value: u64) -> NodeId {
        match NodeId::new(value) {
            Ok(id) => id,
            Err(error) => unreachable!("test fixture uses a valid id: {error}"),
        }
    }

    #[test]
    fn rejects_zero_identity() {
        assert!(NodeId::new(0).is_err());
    }

    #[test]
    fn rejects_duplicate_identity_at_any_depth() {
        let tree = UiNode::new(
            id(1),
            Element::View,
            vec![
                UiNode::new(id(2), Element::View, vec![]),
                UiNode::new(id(2), Element::Text(String::from("duplicate")), vec![]),
            ],
        );

        assert_eq!(UiTree::new(tree), Err(TreeError::DuplicateNodeId(id(2))));
    }

    #[test]
    fn rejects_children_under_text() {
        let tree = UiNode::new(
            id(1),
            Element::Text(String::from("parent")),
            vec![UiNode::new(id(2), Element::View, vec![])],
        );

        assert_eq!(UiTree::new(tree), Err(TreeError::TextHasChildren(id(1))));
    }

    #[test]
    fn accepts_valid_tree() {
        let tree = UiNode::new(
            id(1),
            Element::View,
            vec![UiNode::new(
                id(2),
                Element::Text(String::from("hello")),
                vec![],
            )],
        );

        assert!(UiTree::new(tree).is_ok());
    }
}
