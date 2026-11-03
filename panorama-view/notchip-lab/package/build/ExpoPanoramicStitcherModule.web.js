import { registerWebModule, NativeModule } from "expo";
const UNSUPPORTED = "Panorama stitching is not available on web.";
class ExpoPanoramicStitcherModule extends NativeModule {
    isAvailable() {
        return false;
    }
    helloFromNative(name) {
        return `Hello ${name} (web stub)`;
    }
    async stitchImagePaths() {
        return {
            success: false,
            path: "",
            width: 0,
            height: 0,
            aspectRatio: 0,
            usedIndices: [],
            usedCount: 0,
            geometryJson: "",
            errorMessage: UNSUPPORTED,
        };
    }
    async stitchBase64() {
        return {
            success: false,
            base64Image: "",
            width: 0,
            height: 0,
            usedIndices: [],
            usedCount: 0,
            geometryJson: "",
            errorMessage: UNSUPPORTED,
        };
    }
    async stitchIncrementalBase64() {
        return {
            success: false,
            base64Image: "",
            width: 0,
            height: 0,
            usedIndices: [],
            usedCount: 0,
            geometryJson: "",
            errorMessage: UNSUPPORTED,
        };
    }
}
export default registerWebModule(ExpoPanoramicStitcherModule, "ExpoPanoramicStitcher");
//# sourceMappingURL=ExpoPanoramicStitcherModule.web.js.map