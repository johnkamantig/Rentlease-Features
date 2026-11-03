/**
 * Guidance status for the user, as a machine-readable enum — consumers
 * map these to (localized) display strings, the package never renders
 * copy from the hook.
 *
 *  - `HOLD` covers both "hold still to arm" (the settle window before
 *    shot 0) and "hold, capturing" (inside a capture window) — the user
 *    action is the same.
 *  - `GO_BACK` covers both overshooting the next target and moving
 *    against the locked sweep direction — the user action is the same.
 */
export const SweepStatus = {
    START_TURNING: "START_TURNING",
    KEEP_TURNING: "KEEP_TURNING",
    SLOW_DOWN: "SLOW_DOWN",
    HOLD: "HOLD",
    LEVEL_THE_PHONE: "LEVEL_THE_PHONE",
    GO_BACK: "GO_BACK",
};
//# sourceMappingURL=GuidedSweep.types.js.map