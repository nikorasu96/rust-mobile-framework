#![doc = "Runtime lifecycle and commit orchestration."]

use surface::{
    CreateSurfaceError, StaleSurfaceHandle, SurfaceAccess, SurfaceHandle, SurfaceId,
    SurfaceRegistry,
};

pub mod commit;
pub mod surface;

/// Coordinates runtime-owned surface lifecycle independently of host adapters.
#[derive(Debug)]
pub struct Runtime {
    surfaces: SurfaceRegistry,
}

impl Runtime {
    /// Creates an empty runtime.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            surfaces: SurfaceRegistry::new(),
        }
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
    /// Returns [StaleSurfaceHandle] without mutation when the handle is no longer active.
    pub fn dispose_surface(&mut self, handle: SurfaceHandle) -> Result<(), StaleSurfaceHandle> {
        self.surfaces.dispose(handle)
    }

    /// Admits one callback only while its complete generational handle is live.
    ///
    /// The callback runs at most once and cannot retain the borrowed [SurfaceAccess] proof.
    ///
    /// # Errors
    ///
    /// Returns [StaleSurfaceHandle] without invoking the callback when the handle is stale.
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
}

impl Default for Runtime {
    fn default() -> Self {
        Self::new()
    }
}
