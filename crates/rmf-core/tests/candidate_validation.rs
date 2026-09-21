//! Public contract coverage for declarative candidate validation.

use rmf_core::candidate::{
    CandidateError, CandidateLimits, ComponentKind, DeclarativeNode, FiniteF64, Key, PropertyEntry,
    PropertyId, PropertySet, PropertyValue, ValidatedTree,
};

fn property_id(value: u32) -> PropertyId {
    match PropertyId::new(value) {
        Ok(id) => id,
        Err(error) => unreachable!("test property ID is positive: {error}"),
    }
}

fn properties(entries: Vec<PropertyEntry>) -> PropertySet {
    match PropertySet::new(entries) {
        Ok(properties) => properties,
        Err(error) => unreachable!("test properties are unique: {error}"),
    }
}

fn node(kind: ComponentKind, key: Option<&str>, children: Vec<DeclarativeNode>) -> DeclarativeNode {
    DeclarativeNode::new(
        kind,
        key.map(|value| Key::new(String::from(value))),
        PropertySet::empty(),
        children,
    )
}

#[test]
fn rejects_zero_property_identity() {
    assert!(PropertyId::new(0).is_err());
}

#[test]
fn rejects_non_finite_float_and_canonicalizes_zero() {
    assert!(FiniteF64::new(f64::NAN).is_err());
    assert!(FiniteF64::new(f64::INFINITY).is_err());
    assert_eq!(FiniteF64::new(-0.0), FiniteF64::new(0.0));
}

#[test]
fn property_sets_are_sorted_and_unique() {
    let set = properties(vec![
        PropertyEntry::new(property_id(4), PropertyValue::Bool(true)),
        PropertyEntry::new(property_id(2), PropertyValue::Bool(false)),
    ]);
    assert_eq!(set.entries()[0].id().get(), 2);
    assert_eq!(set.entries()[1].id().get(), 4);
    assert!(
        PropertySet::new(vec![
            PropertyEntry::new(property_id(2), PropertyValue::Bool(true)),
            PropertyEntry::new(property_id(2), PropertyValue::Bool(false)),
        ])
        .is_err()
    );
}

#[test]
fn validates_initial_candidate_without_caller_node_ids() {
    let text = DeclarativeNode::new(
        ComponentKind::Text,
        Some(Key::new(String::from("greeting"))),
        properties(vec![PropertyEntry::new(
            property_id(1),
            PropertyValue::String(String::from("Hello")),
        )]),
        vec![],
    );
    let root = node(ComponentKind::View, None, vec![text]);
    let tree = ValidatedTree::new(root, CandidateLimits::default());

    assert_eq!(tree.map(|tree| tree.node_count()), Ok(2));
}

#[test]
fn rejects_duplicate_sibling_keys() {
    let root = node(
        ComponentKind::View,
        None,
        vec![
            node(ComponentKind::View, Some("same"), vec![]),
            node(ComponentKind::Text, Some("same"), vec![]),
        ],
    );

    assert_eq!(
        ValidatedTree::new(root, CandidateLimits::default()),
        Err(CandidateError::DuplicateSiblingKey(Key::new(String::from(
            "same"
        ))))
    );
}

#[test]
fn rejects_component_property_type_mismatch() {
    let root = DeclarativeNode::new(
        ComponentKind::Text,
        None,
        properties(vec![PropertyEntry::new(
            property_id(1),
            PropertyValue::Bool(true),
        )]),
        vec![],
    );

    assert_eq!(
        ValidatedTree::new(root, CandidateLimits::default()),
        Err(CandidateError::InvalidPropertyType {
            kind: ComponentKind::Text,
            property_id: property_id(1),
        })
    );
}

#[test]
fn rejects_unsupported_component_property() {
    let root = DeclarativeNode::new(
        ComponentKind::View,
        None,
        properties(vec![PropertyEntry::new(
            property_id(1),
            PropertyValue::String(String::from("unsupported")),
        )]),
        vec![],
    );

    assert_eq!(
        ValidatedTree::new(root, CandidateLimits::default()),
        Err(CandidateError::UnsupportedProperty {
            kind: ComponentKind::View,
            property_id: property_id(1),
        })
    );
}

#[test]
fn enforces_depth_and_string_limits() {
    let small = match CandidateLimits::new(1, 1, 1, 1, 3) {
        Ok(limits) => limits,
        Err(error) => unreachable!("fixture limits are positive: {error}"),
    };
    let deep = node(
        ComponentKind::View,
        None,
        vec![node(ComponentKind::View, None, vec![])],
    );
    assert_eq!(
        ValidatedTree::new(deep, small),
        Err(CandidateError::DepthLimitExceeded)
    );

    let long_text = DeclarativeNode::new(
        ComponentKind::Text,
        None,
        properties(vec![PropertyEntry::new(
            property_id(1),
            PropertyValue::String(String::from("four")),
        )]),
        vec![],
    );
    assert_eq!(
        ValidatedTree::new(long_text, small),
        Err(CandidateError::StringLimitExceeded {
            property_id: property_id(1),
        })
    );
}

#[test]
fn public_candidate_values_are_send_and_sync() {
    const fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<DeclarativeNode>();
    assert_send_sync::<ValidatedTree>();
    assert_send_sync::<PropertySet>();
}
