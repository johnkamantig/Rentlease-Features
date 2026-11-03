# Processing decisions and evidence

This prototype now targets a complete horizontal circle. The retained high-level `Stitcher_PANORAMA` function is a regression/comparison tool only. On the 18-frame cyclic synthetic scene it returned OK and used all frames. That result did not expose an exact periodic grid, calibrated angular metadata, or explicit loop-quality validation; the detailed pipeline makes those checks reviewable. No claim is made that the high-level stitcher always fails on circles.

The implementation uses OpenCV SIFT, nearest-neighbor matching/RANSAC, fixed-intrinsic reprojection bundle adjustment, gain compensation, dynamic-programming seams and multiband blending. Ring adjacency bounds matching work and includes the final-to-first constraint. Independent per-edge rotations are checked before global optimization, so optimization cannot simply force a short arc closed. Output projection is explicit inverse equirectangular ray sampling through `cv2.remap`, allowing an exact one-revolution pixel grid and periodic padding. No custom feature matcher, optimizer or generative image pipeline was introduced.

OpenCV's matcher normally zeros confidence above 3 as a close-image heuristic. This discarded excellent textured synthetic overlaps; the pipeline uses a threshold of 4 and its own exact/near-duplicate and angular-motion checks. The installed API supports this option. See [OpenCV matcher source](https://github.com/opencv/opencv/blob/4.x/modules/stitching/src/matchers.cpp).

A full-canvas graph-cut seam experiment was interrupted after several minutes without finishing on dense synthetic texture. Tight bounding rectangles and OpenCV's dynamic-programming color-gradient seam finder brought the complete local test pipeline to approximately 8-10 seconds. This is a local synthetic observation, not a phone benchmark.

Useful primary references:

- [OpenCV detailed Python stitching example](https://github.com/opencv/opencv/blob/4.x/samples/python/stitching_detailed.py): component APIs and interfaces; our pipeline adds explicit calibration, ring validation and periodic export.
- [OpenCV rotation estimation](https://docs.opencv.org/4.13.0/d7/d74/group__stitching__rotation.html): rotation and bundle-adjustment APIs.
- [OpenCV camera calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html): measurement and rectification required before using the restricted camera model.
- [Pannellum configuration reference](https://pannellum.org/documentation/reference/): planned viewer evaluation only; no viewer success is asserted.

No real-room dataset, measured camera calibration or physical Android results are available. Repeated scene textures, translation, mirrors, moving objects and lens distortions remain real-image validation risks. Synthetic fixture generation is isolated under tests and must never be described as real property capture.
