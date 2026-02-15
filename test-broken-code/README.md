# test-broken-code

Synthetic project for ats-benchmark.

Contains intentionally broken patterns:
- SQL injection vectors
- race conditions and shared mutable defaults
- insecure eval/exec usage
- blocking I/O in async code
- swallowed exceptions and retry bugs
- stale cache invalidation bugs
- off-by-one errors and data corruption
- placeholder methods with NotImplementedError

Goal: force benchmark tools to compress/structure large context before LLM repair.
