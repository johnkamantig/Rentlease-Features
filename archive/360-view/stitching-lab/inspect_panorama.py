"""Make six rectilinear inspection views; these do not certify stitching quality."""
import argparse
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image, ImageDraw

from synthetic import render, rotation


def make_sheet(panorama, destination):
    path = Path(destination)
    if path.exists():
        raise ValueError('Inspection output already exists.')
    with Image.open(panorama) as source:
        if source.width != 2 * source.height or source.width * source.height > 40_000_000:
            raise ValueError('Expected bounded 2:1 equirectangular image.')
        image = cv.cvtColor(np.asarray(source.convert('RGB')), cv.COLOR_RGB2BGR)
    size = 512
    intrinsic = np.array([[256, 0, 256], [0, 256, 256], [0, 0, 1]], np.float32)
    sheet = Image.new('RGB', (3 * size, 2 * (size + 32)), '#202020')
    draw = ImageDraw.Draw(sheet)
    for i, (yaw, elevation, label) in enumerate([(0, 0, 'Front'), (90, 0, 'Right'), (180, 0, 'Back / wrap seam'),
                                               (270, 0, 'Left'), (0, 90, 'Ceiling'), (0, -90, 'Floor')]):
        view = render(image, intrinsic, rotation(yaw, elevation), size, size)
        x, y = i % 3 * size, i // 3 * (size + 32)
        sheet.paste(Image.fromarray(cv.cvtColor(view, cv.COLOR_BGR2RGB)), (x, y + 32))
        draw.text((x + 8, y + 8), label, fill='white')
    sheet.save(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('panorama')
    parser.add_argument('output')
    args = parser.parse_args()
    make_sheet(args.panorama, args.output)
