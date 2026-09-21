# Android container ownership contract v1

This contract specifies how the future internal Android host owns one framework root view inside
an application-provided `ViewGroup`. It is below the public `RmfSurfaceHost` API and contains no
domain or reconciliation behavior.

- A container has at most one current host binding.
- A binding receives a positive, monotonic mount ID that is never reused.
- A root must have no parent before attachment and can be attached to one container only.
- Closing a reserved mount cancels attachment; closing an attached mount removes its exact root.
- A late result for an old mount may clean up only its own root and cannot alter a newer binding.
- Repeated or stale releases are harmless.
- Every `ViewGroup` operation is a main-thread effect.

The Python model is an executable specification, not evidence that Android code has compiled.
