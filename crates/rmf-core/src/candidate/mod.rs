//! Declarative candidate values and validation for reconciliation.

use std::collections::HashSet;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::num::NonZeroU32;

/// Closed set of host component kinds supported by the first contract version.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ComponentKind {
    /// Generic layout container.
    View,
    /// Semantic text leaf.
    Text,
}

/// Opaque public key scoped to one sibling list.
#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct Key(String);

impl Key {
    /// Creates a key from its UTF-8 value.
    #[must_use]
    pub fn new(value: String) -> Self {
        Self(value)
    }

    /// Returns the key text.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// Positive numeric property identity from the versioned component schema.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct PropertyId(NonZeroU32);

impl PropertyId {
    /// Creates a positive property identity.
    ///
    /// # Errors
    ///
    /// Returns [`InvalidPropertyId`] when `value` is zero.
    pub const fn new(value: u32) -> Result<Self, InvalidPropertyId> {
        match NonZeroU32::new(value) {
            Some(value) => Ok(Self(value)),
            None => Err(InvalidPropertyId),
        }
    }

    /// Returns the primitive representation.
    #[must_use]
    pub const fn get(self) -> u32 {
        self.0.get()
    }
}

/// Error returned for a zero property identity.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidPropertyId;

impl Display for InvalidPropertyId {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("a property identifier must be non-zero")
    }
}

impl Error for InvalidPropertyId {}

/// Finite, equality-safe floating-point property value.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FiniteF64(u64);

impl FiniteF64 {
    /// Creates a finite value and canonicalizes both signed zero representations.
    ///
    /// # Errors
    ///
    /// Returns [`NonFiniteF64`] for NaN or either infinity.
    pub fn new(value: f64) -> Result<Self, NonFiniteF64> {
        if !value.is_finite() {
            return Err(NonFiniteF64);
        }
        let magnitude_bits = value.to_bits() & 0x7fff_ffff_ffff_ffff;
        let canonical = if magnitude_bits == 0 { 0.0 } else { value };
        Ok(Self(canonical.to_bits()))
    }

    /// Returns the finite primitive representation.
    #[must_use]
    pub const fn get(self) -> f64 {
        f64::from_bits(self.0)
    }
}

/// Error returned for a non-finite floating-point value.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NonFiniteF64;

impl Display for NonFiniteF64 {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("a floating-point property must be finite")
    }
}

impl Error for NonFiniteF64 {}

/// Closed property value family accepted by reconciliation v1.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum PropertyValue {
    /// Boolean value.
    Bool(bool),
    /// Signed 64-bit integer value.
    I64(i64),
    /// Finite canonical floating-point value.
    F64(FiniteF64),
    /// Immutable UTF-8 string value.
    String(String),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum PropertyType {
    Bool,
    I64,
    F64,
    String,
}

impl PropertyValue {
    fn property_type(&self) -> PropertyType {
        match self {
            Self::Bool(_) => PropertyType::Bool,
            Self::I64(_) => PropertyType::I64,
            Self::F64(_) => PropertyType::F64,
            Self::String(_) => PropertyType::String,
        }
    }
}

/// One typed property entry.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PropertyEntry {
    id: PropertyId,
    value: PropertyValue,
}

impl PropertyEntry {
    /// Creates an entry. Component-specific support is checked by [`ValidatedTree`].
    #[must_use]
    pub const fn new(id: PropertyId, value: PropertyValue) -> Self {
        Self { id, value }
    }

    /// Returns the property identity.
    #[must_use]
    pub const fn id(&self) -> PropertyId {
        self.id
    }

    /// Returns the property value.
    #[must_use]
    pub const fn value(&self) -> &PropertyValue {
        &self.value
    }
}

/// Immutable property entries sorted by [`PropertyId`].
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PropertySet(Box<[PropertyEntry]>);

impl PropertySet {
    /// Creates a canonical property set.
    ///
    /// # Errors
    ///
    /// Returns [`DuplicatePropertyId`] when an identity occurs more than once.
    pub fn new(mut entries: Vec<PropertyEntry>) -> Result<Self, DuplicatePropertyId> {
        entries.sort_unstable_by_key(PropertyEntry::id);
        if entries.windows(2).any(|pair| pair[0].id == pair[1].id) {
            return Err(DuplicatePropertyId);
        }
        Ok(Self(entries.into_boxed_slice()))
    }

    /// Creates an empty property set.
    #[must_use]
    pub fn empty() -> Self {
        Self(Box::new([]))
    }

    /// Returns canonical entries in ascending identity order.
    #[must_use]
    pub fn entries(&self) -> &[PropertyEntry] {
        &self.0
    }
}

/// Error returned for duplicate identities within one property set.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DuplicatePropertyId;

impl Display for DuplicatePropertyId {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("a property identity may occur only once")
    }
}

impl Error for DuplicatePropertyId {}

/// Candidate node without a runtime-owned node identity.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DeclarativeNode {
    kind: ComponentKind,
    key: Option<Key>,
    properties: PropertySet,
    children: Box<[Self]>,
}

impl DeclarativeNode {
    /// Creates an unvalidated declarative node.
    #[must_use]
    pub fn new(
        kind: ComponentKind,
        key: Option<Key>,
        properties: PropertySet,
        children: Vec<Self>,
    ) -> Self {
        Self {
            kind,
            key,
            properties,
            children: children.into_boxed_slice(),
        }
    }

    /// Returns the component kind.
    #[must_use]
    pub const fn kind(&self) -> ComponentKind {
        self.kind
    }

    /// Returns the optional sibling-scoped key.
    #[must_use]
    pub fn key(&self) -> Option<&Key> {
        self.key.as_ref()
    }

    /// Returns the canonical property set.
    #[must_use]
    pub fn properties(&self) -> &PropertySet {
        &self.properties
    }

    /// Returns children in declaration order.
    #[must_use]
    pub fn children(&self) -> &[Self] {
        &self.children
    }
}

/// Defensive candidate-tree limits.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CandidateLimits {
    max_depth: usize,
    max_nodes: usize,
    max_children_per_node: usize,
    max_properties_per_node: usize,
    max_string_bytes: usize,
}

impl CandidateLimits {
    /// Creates positive limits.
    ///
    /// # Errors
    ///
    /// Returns [`InvalidCandidateLimits`] when any limit is zero.
    pub const fn new(
        max_depth: usize,
        max_nodes: usize,
        max_children_per_node: usize,
        max_properties_per_node: usize,
        max_string_bytes: usize,
    ) -> Result<Self, InvalidCandidateLimits> {
        if max_depth == 0
            || max_nodes == 0
            || max_children_per_node == 0
            || max_properties_per_node == 0
            || max_string_bytes == 0
        {
            return Err(InvalidCandidateLimits);
        }
        Ok(Self {
            max_depth,
            max_nodes,
            max_children_per_node,
            max_properties_per_node,
            max_string_bytes,
        })
    }
}

impl Default for CandidateLimits {
    fn default() -> Self {
        Self {
            max_depth: 256,
            max_nodes: 100_000,
            max_children_per_node: 10_000,
            max_properties_per_node: 256,
            max_string_bytes: 1_048_576,
        }
    }
}

/// Error returned when a defensive limit is zero.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidCandidateLimits;

impl Display for InvalidCandidateLimits {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("candidate limits must be positive")
    }
}

impl Error for InvalidCandidateLimits {}

/// Opaque declarative tree that passed all v1 candidate checks.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ValidatedTree {
    root: DeclarativeNode,
    node_count: usize,
}

impl ValidatedTree {
    /// Validates and owns a candidate tree.
    ///
    /// # Errors
    ///
    /// Returns [`CandidateError`] for structural, schema or defensive-limit failures.
    pub fn new(
        root: DeclarativeNode,
        limits: CandidateLimits,
    ) -> Result<Self, CandidateError> {
        let node_count = validate_node(&root, limits, 1)?;
        Ok(Self { root, node_count })
    }

    /// Returns the validated root.
    #[must_use]
    pub const fn root(&self) -> &DeclarativeNode {
        &self.root
    }

    /// Returns the validated total node count.
    #[must_use]
    pub const fn node_count(&self) -> usize {
        self.node_count
    }
}

/// Typed candidate validation failure.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CandidateError {
    /// The tree exceeds the configured depth.
    DepthLimitExceeded,
    /// The tree exceeds the configured total node count.
    NodeLimitExceeded,
    /// One node exceeds the configured direct-child count.
    ChildLimitExceeded,
    /// One node exceeds the configured property count.
    PropertyLimitExceeded,
    /// One string property exceeds the configured UTF-8 byte count.
    StringLimitExceeded {
        /// Oversized string property identity.
        property_id: PropertyId,
    },
    /// A text leaf contains children.
    TextHasChildren,
    /// A key occurs more than once in one sibling list.
    DuplicateSiblingKey(Key),
    /// A property is not registered for its component kind.
    UnsupportedProperty {
        /// Component containing the property.
        kind: ComponentKind,
        /// Unsupported property identity.
        property_id: PropertyId,
    },
    /// A property value does not match its registered type.
    InvalidPropertyType {
        /// Component containing the property.
        kind: ComponentKind,
        /// Mismatched property identity.
        property_id: PropertyId,
    },
}

impl Display for CandidateError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::DepthLimitExceeded => formatter.write_str("candidate depth limit exceeded"),
            Self::NodeLimitExceeded => formatter.write_str("candidate node limit exceeded"),
            Self::ChildLimitExceeded => formatter.write_str("candidate child limit exceeded"),
            Self::PropertyLimitExceeded => {
                formatter.write_str("candidate property limit exceeded")
            }
            Self::StringLimitExceeded { property_id } => write!(
                formatter,
                "string property {} exceeds its byte limit",
                property_id.get()
            ),
            Self::TextHasChildren => formatter.write_str("a text candidate cannot have children"),
            Self::DuplicateSiblingKey(key) => {
                write!(formatter, "duplicate sibling key: {}", key.as_str())
            }
            Self::UnsupportedProperty { kind, property_id } => write!(
                formatter,
                "property {} is unsupported by {kind:?}",
                property_id.get()
            ),
            Self::InvalidPropertyType { kind, property_id } => write!(
                formatter,
                "property {} has an invalid type for {kind:?}",
                property_id.get()
            ),
        }
    }
}

impl Error for CandidateError {}

fn validate_node(
    node: &DeclarativeNode,
    limits: CandidateLimits,
    depth: usize,
) -> Result<usize, CandidateError> {
    if depth > limits.max_depth {
        return Err(CandidateError::DepthLimitExceeded);
    }
    if node.children.len() > limits.max_children_per_node {
        return Err(CandidateError::ChildLimitExceeded);
    }
    if node.properties.entries().len() > limits.max_properties_per_node {
        return Err(CandidateError::PropertyLimitExceeded);
    }
    if node.kind == ComponentKind::Text && !node.children.is_empty() {
        return Err(CandidateError::TextHasChildren);
    }
    validate_properties(node, limits)?;

    let mut keys = HashSet::new();
    let mut node_count = 1usize;
    for child in &node.children {
        if let Some(key) = child.key() {
            if !keys.insert(key.as_str()) {
                return Err(CandidateError::DuplicateSiblingKey(key.clone()));
            }
        }
        let child_depth = depth
            .checked_add(1)
            .ok_or(CandidateError::DepthLimitExceeded)?;
        let child_count = validate_node(child, limits, child_depth)?;
        node_count = node_count
            .checked_add(child_count)
            .ok_or(CandidateError::NodeLimitExceeded)?;
        if node_count > limits.max_nodes {
            return Err(CandidateError::NodeLimitExceeded);
        }
    }
    Ok(node_count)
}

fn validate_properties(
    node: &DeclarativeNode,
    limits: CandidateLimits,
) -> Result<(), CandidateError> {
    for entry in node.properties.entries() {
        let expected = property_schema(node.kind, entry.id).ok_or(
            CandidateError::UnsupportedProperty {
                kind: node.kind,
                property_id: entry.id,
            },
        )?;
        if expected != entry.value.property_type() {
            return Err(CandidateError::InvalidPropertyType {
                kind: node.kind,
                property_id: entry.id,
            });
        }
        if let PropertyValue::String(value) = &entry.value {
            if value.len() > limits.max_string_bytes {
                return Err(CandidateError::StringLimitExceeded {
                    property_id: entry.id,
                });
            }
        }
    }
    Ok(())
}

const fn property_schema(kind: ComponentKind, property_id: PropertyId) -> Option<PropertyType> {
    match (kind, property_id.get()) {
        (ComponentKind::View, 2) | (ComponentKind::Text, 2) => Some(PropertyType::Bool),
        (ComponentKind::View, 3) => Some(PropertyType::I64),
        (ComponentKind::View, 4) | (ComponentKind::Text, 4) => Some(PropertyType::F64),
        (ComponentKind::Text, 1) => Some(PropertyType::String),
        _ => None,
    }
}
