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
/** Fire the capture-success haptic if expo-haptics is installed; never throws. */
export declare function hapticShotFeedback(): void;
export type ScreenInsets = {
    top: number;
    right: number;
    bottom: number;
    left: number;
};
/**
 * `useSafeAreaInsets` when available, fixed fallback insets otherwise.
 * The branch is constant for the life of the app (module-load feature
 * detection), so the hook call order is stable across renders.
 */
export declare function useScreenInsets(): ScreenInsets;
//# sourceMappingURL=optionalDeps.d.ts.map