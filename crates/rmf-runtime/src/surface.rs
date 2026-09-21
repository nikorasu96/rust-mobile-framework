//! Runtime-owned surface identities and lifecycle registry.

use std::collections::BTreeMap;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::marker::PhantomData;
use std::num::NonZeroU64;

/// Positive logical identity selected by a runtime caller.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct SurfaceId(NonZeroU64);

impl SurfaceId {
    /// Creates a positive surface identity.
    ///
    /// # Errors
    ///
    /// Returns [`InvalidSurfaceId`] when `value` is zero.
    pub const fn new(value: u64) -> Result<Self, InvalidSurfaceId> {
        match NonZeroU64::new(value) {
            Some(value) => Ok(Self(value)),
            None => Err(InvalidSurfaceId),
        }
    }

    /// Returns the primitive transport representation.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0.get()
    }
}

/// Error returned when constructing a zero surface identity.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidSurfaceId;

impl Display for InvalidSurfaceId {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("a surface identifier must be non-zero")
    }
}

impl Error for InvalidSurfaceId {}

/// Runtime-assigned generation that is never reused by one registry.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct SurfaceGeneration(NonZeroU64);

impl SurfaceGeneration {
    /// Returns the primitive transport representation.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0.get()
    }
}

/// Complete identity required for disposal and callback admission.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SurfaceHandle {
    surface_id: SurfaceId,
    generation: SurfaceGeneration,
}

impl SurfaceHandle {
    /// Returns the logical surface identity.
    #[must_use]
    pub const fn surface_id(self) -> SurfaceId {
        self.surface_id
    }

    /// Returns the runtime-assigned generation.
    #[must_use]
    pub const fn generation(self) -> SurfaceGeneration {
        self.generation
    }
}

/// Error returned when creating a surface.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CreateSurfaceError {
    /// The logical identity already has a live generation.
    AlreadyActive(SurfaceId),
    /// Every positive `u64` generation has been consumed.
    GenerationExhausted,
}

impl Display for CreateSurfaceError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::AlreadyActive(surface_id) => {
                write!(formatter, "surface {} is already active", surface_id.get())
            }
            Self::GenerationExhausted => formatter.write_str("surface generation exhausted"),
        }
    }
}

impl Error for CreateSurfaceError {}

/// Error returned when a complete handle is no longer active.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct StaleSurfaceHandle {
    handle: SurfaceHandle,
}

impl StaleSurfaceHandle {
    /// Returns the rejected handle for structured diagnostics.
    #[must_use]
    pub const fn handle(self) -> SurfaceHandle {
        self.handle
    }
}

impl Display for StaleSurfaceHandle {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "surface handle ({}, {}) is stale",
            self.handle.surface_id.get(),
            self.handle.generation.get()
        )
    }
}

impl Error for StaleSurfaceHandle {}

/// Proof that a handle resolved while its registry remained borrowed.
#[derive(Debug)]
pub struct SurfaceAccess<'registry> {
    handle: SurfaceHandle,
    registry: PhantomData<&'registry SurfaceRegistry>,
}

impl SurfaceAccess<'_> {
    /// Returns the exact live handle that was resolved.
    #[must_use]
    pub const fn handle(&self) -> SurfaceHandle {
        self.handle
    }
}

/// Serialized registry for live surfaces and monotonic generations.
#[derive(Debug)]
pub struct SurfaceRegistry {
    next_generation: Option<NonZeroU64>,
    active: BTreeMap<SurfaceId, SurfaceGeneration>,
}

impl Default for SurfaceRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl SurfaceRegistry {
    /// Creates an empty registry whose first generation is one.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            next_generation: NonZeroU64::new(1),
            active: BTreeMap::new(),
        }
    }

    /// Creates one live generation for `surface_id`.
    ///
    /// # Errors
    ///
    /// Returns [`CreateSurfaceError::AlreadyActive`] for a duplicate logical slot or
    /// [`CreateSurfaceError::GenerationExhausted`] after the allocator reaches `u64::MAX`.
    pub fn create(&mut self, surface_id: SurfaceId) -> Result<SurfaceHandle, CreateSurfaceError> {
        if self.active.contains_key(&surface_id) {
            return Err(CreateSurfaceError::AlreadyActive(surface_id));
        }
        let raw_generation = self
            .next_generation
            .ok_or(CreateSurfaceError::GenerationExhausted)?;
        let generation = SurfaceGeneration(raw_generation);
        self.next_generation = raw_generation
            .get()
            .checked_add(1)
            .and_then(NonZeroU64::new);
        self.active.insert(surface_id, generation);
        Ok(SurfaceHandle {
            surface_id,
            generation,
        })
    }

    /// Invalidates the exact live handle before platform cleanup starts.
    ///
    /// # Errors
    ///
    /// Returns [`StaleSurfaceHandle`] without mutation when the pair is not live.
    pub fn dispose(&mut self, handle: SurfaceHandle) -> Result<(), StaleSurfaceHandle> {
        if self.active.get(&handle.surface_id) != Some(&handle.generation) {
            return Err(StaleSurfaceHandle { handle });
        }
        self.active.remove(&handle.surface_id);
        Ok(())
    }

    /// Resolves a complete handle for inbound callback admission.
    ///
    /// # Errors
    ///
    /// Returns [`StaleSurfaceHandle`] when the logical slot is absent or has another generation.
    pub fn resolve(&self, handle: SurfaceHandle) -> Result<SurfaceAccess<'_>, StaleSurfaceHandle> {
        if self.active.get(&handle.surface_id) != Some(&handle.generation) {
            return Err(StaleSurfaceHandle { handle });
        }
        Ok(SurfaceAccess {
            handle,
            registry: PhantomData,
        })
    }

    /// Returns the number of currently live logical surfaces.
    #[must_use]
    pub fn active_count(&self) -> usize {
        self.active.len()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        CreateSurfaceError, StaleSurfaceHandle, SurfaceGeneration, SurfaceHandle, SurfaceId,
        SurfaceRegistry,
    };
    use std::collections::BTreeMap;
    use std::num::NonZeroU64;

    fn id(value: u64) -> SurfaceId {
        match SurfaceId::new(value) {
            Ok(surface_id) => surface_id,
            Err(error) => unreachable!("test fixture uses a positive surface ID: {error}"),
        }
    }

    fn create(registry: &mut SurfaceRegistry, surface_id: SurfaceId) -> SurfaceHandle {
        match registry.create(surface_id) {
            Ok(handle) => handle,
            Err(error) => unreachable!("test fixture can create its surface: {error}"),
        }
    }

    #[test]
    fn rejects_zero_surface_identity() {
        assert_eq!(SurfaceId::new(0), Err(super::InvalidSurfaceId));
    }

    #[test]
    fn rejects_duplicate_without_consuming_generation() {
        let mut registry = SurfaceRegistry::new();
        let first = create(&mut registry, id(7));

        assert_eq!(
            registry.create(id(7)),
            Err(CreateSurfaceError::AlreadyActive(id(7)))
        );
        assert_eq!(create(&mut registry, id(8)).generation().get(), 2);
        assert_eq!(first.generation().get(), 1);
    }

    #[test]
    fn recreated_slot_rejects_prior_generation() {
        let mut registry = SurfaceRegistry::new();
        let stale = create(&mut registry, id(7));
        assert_eq!(registry.dispose(stale), Ok(()));
        let current = create(&mut registry, id(7));

        assert_eq!(
            registry.resolve(stale).err(),
            Some(StaleSurfaceHandle { handle: stale })
        );
        assert_eq!(
            registry.dispose(stale),
            Err(StaleSurfaceHandle { handle: stale })
        );
        assert_eq!(
            registry.resolve(current).map(|access| access.handle()),
            Ok(current)
        );
    }

    #[test]
    fn disposal_isolated_from_another_surface() {
        let mut registry = SurfaceRegistry::new();
        let first = create(&mut registry, id(1));
        let second = create(&mut registry, id(2));

        assert_eq!(registry.dispose(first), Ok(()));
        assert!(registry.resolve(second).is_ok());
        assert_eq!(registry.active_count(), 1);
    }

    #[test]
    fn maximum_generation_is_used_once_then_exhausts() {
        let Some(maximum) = NonZeroU64::new(u64::MAX) else {
            unreachable!("u64::MAX is non-zero");
        };
        let mut registry = SurfaceRegistry {
            next_generation: Some(maximum),
            active: BTreeMap::default(),
        };
        let last = create(&mut registry, id(1));

        assert_eq!(last.generation(), SurfaceGeneration(maximum));
        assert_eq!(
            registry.create(id(2)),
            Err(CreateSurfaceError::GenerationExhausted)
        );
        assert_eq!(registry.active_count(), 1);
    }

    #[test]
    fn public_values_are_send_and_sync() {
        const fn assert_send_sync<T: Send + Sync>() {}
        assert_send_sync::<SurfaceId>();
        assert_send_sync::<SurfaceGeneration>();
        assert_send_sync::<SurfaceHandle>();
        assert_send_sync::<SurfaceRegistry>();
    }
}
