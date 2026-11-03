"""Deterministic test-only sphere, sampled through perspective cameras.

This is geometry test data, never property imagery. No linear-strip crops.
"""
import cv2
import numpy as np


def cyclic_scene(headings=None, width=320, height=480, hfov=50):
    rng = np.random.default_rng(730)
    texture = rng.integers(30, 225, (768, 1536, 3), dtype=np.uint8)
    texture = cv2.resize(texture, (3072, 1536))
    for _ in range(6500):
        x, y = rng.integers([0, 0], [3072, 1536])
        cv2.circle(texture, (int(x), int(y)), int(rng.integers(2, 12)),
                   tuple(int(c) for c in rng.integers(20, 240, 3)), -1)
    # Blur with periodic longitude, including the texture's wrap boundary.
    texture = cv2.GaussianBlur(np.pad(texture, ((0, 0), (8, 8), (0, 0)), mode="wrap"), (5, 5), 0)[:, 8:-8]
    f = width / (2 * np.tan(np.deg2rad(hfov / 2)))
    x, y = np.meshgrid((np.arange(width) - width / 2) / f,
                       (np.arange(height) - height / 2) / f)
    rays = np.stack([x, y, np.ones_like(x)], -1)
    frames = []
    for heading in (np.arange(0, 360, 20) if headings is None else headings):
        a = np.deg2rad(heading)
        rotation = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        world = rays @ rotation.T
        lon = np.arctan2(world[..., 0], world[..., 2])
        lat = np.arctan2(world[..., 1], np.hypot(world[..., 0], world[..., 2]))
        mx = ((lon / (2 * np.pi) + .5) * texture.shape[1]).astype(np.float32)
        my = ((lat / np.pi + .5) * texture.shape[0]).astype(np.float32)
        frames.append(cv2.remap(texture, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP))
    return frames, texture
