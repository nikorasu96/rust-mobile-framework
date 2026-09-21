# Android Kotlin facade lifecycle contract v1

This contract specifies the observable lifecycle of the future
`dev.rmf.android.RmfSurfaceHost`. It separates public any-thread requests from native results and
callbacks that must already be on Android's main thread.

The model guarantees:

- worker-thread create and close requests post exactly one task to the main queue;
- closing is idempotent and native disposal is requested at most once;
- a close racing with native creation disposes the newly created handle before it becomes active;
- cancelled queued tasks cannot resurrect a closed facade;
- callbacks require the current generational handle and a strictly increasing sequence;
- callbacks are never delivered after close has been requested;
- native create/dispose failure is terminal and visible rather than silently treated as success.

Run the reviewed scenarios from the repository root:

```text
python3 scripts/check_android_facade_fixtures.py
python3 scripts/check_android_facade_exhaustive.py
```

The second command explores every state/action pair reachable to depth seven within its documented
two-handle, two-sequence domain. This is a language-independent state contract, not an unbounded
formal proof. Passing it does not claim Kotlin compilation, Android lifecycle integration, a
working JNI library or device execution.
