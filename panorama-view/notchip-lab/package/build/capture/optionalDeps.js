/**
 * Optional peer dependencies, feature-detected at module load.
 *
 * The requires are literal and wrapped in try/catch so Metro treats
 * them as optional dependencies (expo's default metro config enables
 * `transformer.allowOptionalDependencies`): a missing package neither
 * fails the consumer's bundle nor throws at runtime. Do NOT convert
 * these to static `import` — that would make the packages hard
 * requirements again.
 */
let Haptics = null;
try {
    Haptics = require("expo-haptics");
}
catch {
    Haptics = null;
}
/** Fire the capture-success haptic if expo-haptics is installed; never throws. */
export function hapticShotFeedback() {
    if (!Haptics)
        return;
    try {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).then(() => undefined, () => undefined);
    }
    catch {
        // Haptics are strictly best-effort.
    }
}
const FALLBACK_INSETS = {
    top: 24,
    right: 0,
    bottom: 16,
    left: 0,
};
let realUseSafeAreaInsets = null;
try {
    realUseSafeAreaInsets = require("react-native-safe-area-context").useSafeAreaInsets;
}
catch {
    realUseSafeAreaInsets = null;
}
/**
 * `useSafeAreaInsets` when available, fixed fallback insets otherwise.
 * The branch is constant for the life of the app (module-load feature
 * detection), so the hook call order is stable across renders.
 */
export function useScreenInsets() {
    if (!realUseSafeAreaInsets)
        return FALLBACK_INSETS;
    try {
        return realUseSafeAreaInsets();
    }
    catch {
        // Library present but no <SafeAreaProvider> mounted above us.
        return FALLBACK_INSETS;
    }
}
//# sourceMappingURL=optionalDeps.js.map