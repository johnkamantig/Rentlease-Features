# Historical baseline results

The original prototype came with a report of 15 passing tests in a Linux sandbox. Those were tests of a wide-image stitch and did not verify a circle, calibrated projection or viewer. They are historical evidence only.

On 2026-10-29 the unchanged 15 tests were rerun in this Windows checkout and passed in 9.55 seconds. The old rectangular border crop and mocked success export were subsequently replaced with full-width mask coverage and real cyclic export tests. Reusable ingestion, error, compression and baseline regression checks remain.

Current Phase 1-2 changes, commands, measurements and limitations are in [PHASE_RESULTS.md](PHASE_RESULTS.md). No authentic room-photo or Android success is recorded.
