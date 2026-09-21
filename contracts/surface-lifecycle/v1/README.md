# Surface lifecycle contract fixtures v1

These fixtures specify creation, disposal and callback routing using positive generational
handles. They are independent of Android objects, JNI representation and rendering behavior.

Run them with:

```bash
python3 scripts/check_surface_lifecycle_fixtures.py
python3 scripts/check_surface_lifecycle_sequences.py
python3 scripts/check_surface_lifecycle_exhaustive.py
```

Generations are process-wide, monotonic and never reused. Every callback and disposal operation
must present the exact active `(surface_id, generation)` pair. Reusing a logical surface ID creates
a new generation, so delayed work from its predecessor fails closed.

A complementary fixed-seed campaign executes repeated operations across eight logical slots,
retains disposed handles for adversarial callbacks and verifies registry isolation after every
transition. It is deterministic property-style testing, not coverage-guided fuzzing.

The bounded explorer applies every create action and every callback/disposal handle in a small,
documented domain to each reachable registry state. Equivalent states at a depth are merged. This
is exhaustive for that bound and domain, not an unbounded formal proof.
