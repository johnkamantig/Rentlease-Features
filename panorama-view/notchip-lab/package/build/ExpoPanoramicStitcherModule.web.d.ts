import { NativeModule } from "expo";
import type { ExpoPanoramicStitcherModuleEvents, NativeStitchBase64Result, NativeStitchResult } from "./ExpoPanoramicStitcher.types";
declare class ExpoPanoramicStitcherModule extends NativeModule<ExpoPanoramicStitcherModuleEvents> {
    isAvailable(): boolean;
    helloFromNative(name: string): string;
    stitchImagePaths(): Promise<NativeStitchResult>;
    stitchBase64(): Promise<NativeStitchBase64Result>;
    stitchIncrementalBase64(): Promise<NativeStitchBase64Result>;
}
declare const _default: typeof ExpoPanoramicStitcherModule;
export default _default;
//# sourceMappingURL=ExpoPanoramicStitcherModule.web.d.ts.map