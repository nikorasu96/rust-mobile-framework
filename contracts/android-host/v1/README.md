# Android host composition contract v1

This contract joins the already reviewed facade, `ViewGroup` ownership, and generational surface
lifecycle models. It adds orchestration only; it does not redefine any sub-contract or claim an
implemented Kotlin/JNI adapter.

The root is attached synchronously on Android's main thread before native surface creation is
requested. Close removes only that host's root. A native create result that arrives after close is
disposed immediately, and callbacks must pass the generational-handle gate before reaching the
facade sequence gate.

Run `python3 scripts/check_android_host_composition.py` from the repository root.
