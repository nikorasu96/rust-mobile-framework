# Android FFI contract v1

This directory specifies admission to the future Android JNI adapter. It is deliberately smaller
than the runtime and lifecycle contracts: accepted input still must pass the relevant runtime
operation.

`contract.json` fixes the JVM descriptor, operation numbers, response status numbers, byte order,
response header, operation-payload header and limits.
Every fixture is a closed object with:

- `input`: the exact JNI primitive values plus `caller_thread`, a harness observation rather than
  an ABI argument;
- `expected`: either an accepted normalized request or a stable boundary rejection;
- hexadecimal payloads so fixtures remain encoding-independent and contain no borrowed objects.

Event and commit-result payloads begin with `RMP1`, schema version, operation code, body length and
four reserved zero bytes. Their bodies are fixed at 24 bytes. V1 events contain a positive node
identity, the sole registered `CLICK` code and a positive sequence. Commit results contain
consecutive revisions and a closed outcome/reason pair matching ADR-0004. Flags and reserved
fields must be zero. No body transports strings, native pointers or platform objects.

The frame corpus checks framing independently. The typed-body corpus rejects wrong sizes,
identities, event codes, sequences, flags, revisions, enum values and invalid outcome/reason
pairs. Response frames receive equivalent framing validation. Decoders require complete input and
never use an untrusted length to allocate.

`mutation-campaign.json` defines seven canonical packets. Its checker flips every bit exactly once
and requires each of the 2,128 resulting packets either to fail with a registered decoder code or
to decode and re-encode byte-for-byte as a canonical valid message. This complements the reviewed
corpora; it does not replace truncation and wrong-size cases that cannot result from a bit flip.

Run from the repository root:

```text
python3 scripts/check_android_ffi_fixtures.py
python3 scripts/check_android_ffi_frame_corpus.py
python3 scripts/check_android_ffi_body_corpus.py
python3 scripts/check_android_ffi_mutations.py
python3 -m unittest discover -s scripts/tests -v
```

Passing these fixtures does not claim a compiled Rust ABI, live JNI registration, CheckJNI,
Kotlin type checking, emulator execution or panic containment. Those are later acceptance gates.
