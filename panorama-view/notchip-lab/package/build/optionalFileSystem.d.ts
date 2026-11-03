/**
 * Optional `expo-file-system` access for the sweep-manifest sidecar.
 *
 * `expo-file-system` is an optional peer: every Expo app has it (the `expo`
 * package depends on it), but the core stitcher must keep working — and the
 * consumer's bundle must keep building — when it is absent. The require is
 * therefore a LITERAL `require("expo-file-system")` inside `try/catch`,
 * exactly like `src/capture/optionalDeps.ts`: Metro's
 * `transformer.allowOptionalDependencies` (Expo's default metro config)
 * treats a require inside a try block as optional, so a missing package
 * neither fails the bundle nor throws at runtime. Do NOT convert this to a
 * static `import` and do not compute the module id.
 *
 * The load is lazy (first write, not module load) and memoized, so
 * consumers who never write a sidecar never touch the module.
 */
/**
 * A `file://` URI for a bare filesystem path; anything that already has a
 * URL scheme is returned untouched. `expo-file-system`'s `File` rejects
 * scheme-less paths on iOS, so every path goes through this.
 */
export declare function toFileUri(path: string): string;
/**
 * Write `text` to `path` (bare path or `file://` URI) with
 * `expo-file-system`'s synchronous `File.write` (SDK 56+). Creates the file,
 * not its parent directories. Throws when `expo-file-system` is not
 * installed or the write fails — callers treat it as best-effort.
 */
export declare function writeTextFile(path: string, text: string): void;
//# sourceMappingURL=optionalFileSystem.d.ts.map