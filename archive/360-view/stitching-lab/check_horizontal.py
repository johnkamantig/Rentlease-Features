"""Repeatable local input/overlap screen, with pictures to inspect. Does not stitch."""
import argparse
import json
from pathlib import Path

import cv2 as cv
import numpy as np
from PIL import Image, ImageDraw

from inputs import InputError
from prepare_horizontal import prepare


def passes_screen(row):
    # Experimental evidence thresholds, not a panorama quality certificate.
    return (row.get('ransac_inliers', 0) >= 15 and row.get('inlier_ratio', 0) >= .5
            and min(row.get('inlier_hull_fraction_a', 0), row.get('inlier_hull_fraction_b', 0)) >= .01)


def match_pair(a, b, feature_a, feature_b):
    ka, da = feature_a
    kb, db = feature_b
    matches = []
    if da is not None and db is not None and len(da) >= 2 and len(db) >= 2:
        matcher = cv.BFMatcher(cv.NORM_L2)
        forward = [m for pair in matcher.knnMatch(da, db, k=2) if len(pair) == 2
                   for m, n in [pair] if m.distance < .75 * n.distance]
        reverse = {(m.trainIdx, m.queryIdx) for pair in matcher.knnMatch(db, da, k=2) if len(pair) == 2
                   for m, n in [pair] if m.distance < .75 * n.distance}
        matches = [m for m in forward if (m.queryIdx, m.trainIdx) in reverse]
    row = {'keypoints_a': len(ka), 'keypoints_b': len(kb), 'mutual_ratio_matches': len(matches)}
    accepted = np.zeros(len(matches), dtype=bool)
    if len(matches) >= 4:
        points_a = np.float32([ka[m.queryIdx].pt for m in matches])
        points_b = np.float32([kb[m.trainIdx].pt for m in matches])
        cv.setRNGSeed(0)
        homography, mask = cv.findHomography(points_a, points_b, cv.RANSAC, 3, maxIters=5000, confidence=.995)
        if homography is not None and mask is not None:
            accepted = mask.ravel().astype(bool)
            count = int(accepted.sum())
            row.update(ransac_inliers=count, inlier_ratio=count / len(matches))
            if count:
                predicted = cv.perspectiveTransform(points_a[accepted, None, :], homography)[:, 0, :]
                row['median_fit_error_work_pixels'] = float(np.median(np.linalg.norm(predicted - points_b[accepted], axis=1)))
            for label, points, image in [('a', points_a, a), ('b', points_b, b)]:
                row['inlier_hull_fraction_' + label] = (float(cv.contourArea(cv.convexHull(points[accepted])) / (image.shape[0] * image.shape[1]))
                                                       if count >= 3 else 0)
    row['enough_for_further_investigation'] = passes_screen(row)
    # Lines are algorithm-selected correspondences; even displayed inliers may be WRONG.
    drawing = cv.drawMatches(a, ka, b, kb, matches, None, matchesMask=accepted.astype(int).tolist(),
                             flags=cv.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    return row, drawing


def check(input_path, output_path):
    if prepare(input_path, output_path) != 0:
        return 2
    output = Path(output_path).resolve()
    prepared = json.loads((output / 'prepared.json').read_text(encoding='utf-8'))
    photos = prepared['photos']
    report = {'status': 'failed', 'opencv': cv.__version__, 'photo_count': len(photos),
              'panorama_generated': False, 'coverage_validated': False, 'visual_inspection_performed': False,
              'method': 'SIFT max side 1920, max 6000 features; mutual ratio 0.75; RANSAC 3px, 5000 iterations, confidence .995; seed 0, one thread',
              'thresholds': '15 inliers, ratio >= 0.5, feature hull >= 1% in both images',
              'warning': 'Feature hull is not overlap percentage. Inliers and low errors can be false matches. Inspect the pictures. No stitchability guarantee.',
              'keypoints': [], 'adjacent_pairs': []}
    try:
        cv.setNumThreads(1)
        cv.setRNGSeed(0)
        finder = cv.SIFT_create(nfeatures=6000)
        cols = min(4, len(photos))
        sheet = Image.new('RGB', (cols * 240, ((len(photos) + cols - 1) // cols) * 360), '#202020')
        labels = ImageDraw.Draw(sheet)
        previous, previous_features = None, None
        for index, photo in enumerate(photos):
            image = cv.imread(str(output / photo['path']))
            if image is None:
                raise InputError(f'Could not decode prepared photo {index + 1}.')
            scale = min(1, 1920 / max(image.shape[:2]))
            image = cv.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)), interpolation=cv.INTER_AREA)
            features = finder.detectAndCompute(cv.cvtColor(image, cv.COLOR_BGR2GRAY), None)
            report['keypoints'].append(len(features[0]))
            thumb = Image.fromarray(cv.cvtColor(image, cv.COLOR_BGR2RGB))
            thumb.thumbnail((240, 320))
            x, y = (index % cols) * 240, (index // cols) * 360
            sheet.paste(thumb, (x, y + 32))
            labels.text((x + 6, y + 8), f'Photo {index + 1} | guide {photo["targetYaw"]} deg', fill='white')
            if previous is not None:
                row, drawing = match_pair(previous, image, previous_features, features)
                row.update(a=index, b=index + 1)
                name = f'matches-{index}-{index + 1}.jpg'
                factor = min(1, 1200 / max(drawing.shape[:2]))
                drawing = cv.resize(drawing, (round(drawing.shape[1] * factor), round(drawing.shape[0] * factor)))
                caption = f'Photos {index}-{index+1}: algorithm matches, NOT verified. Lines must join the SAME detail.'
                picture = Image.fromarray(cv.cvtColor(drawing, cv.COLOR_BGR2RGB))
                labelled = Image.new('RGB', (picture.width, picture.height + 30), '#202020')
                labelled.paste(picture, (0, 30))
                ImageDraw.Draw(labelled).text((6, 8), caption, fill='white')
                labelled.save(output / name)
                row['picture'] = name
                report['adjacent_pairs'].append(row)
            previous, previous_features = image, features
        sheet.save(output / 'contact-sheet.jpg')
        all_pass = all(p['enough_for_further_investigation'] for p in report['adjacent_pairs'])
        report['status'] = 'screen_passed_needs_visual_review' if all_pass else 'weak_connections'
        lines = [f'Input checks passed: {len(photos)}/{len(photos)} photos.', '', 'Neighboring photos | inliers | screening result']
        for pair in report['adjacent_pairs']:
            result = 'STRONGER - inspect manually' if pair['enough_for_further_investigation'] else 'WEAK - inspect overlap'
            lines.append(f'{pair["a"]}-{pair["b"]} | {pair.get("ransac_inliers", 0)} | {result}')
        lines += ['', 'Open contact-sheet.jpg, then matches-A-B.jpg for each join.',
                  'A line must connect the same physical detail in both photos. Different objects = false match.',
                  'Many lines on repeated curtain rings/tiles can still be wrong.',
                  'Four points can fit a homography exactly even when they are incorrect.',
                  'No percentage of actual image overlap is measured. No panorama was generated.',
                  'This screen does not guarantee stitching success or prove a weak pair is impossible to stitch.']
        (output / 'CHECK_RESULTS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('\n'.join(lines))
    except (InputError, OSError, ValueError, MemoryError, cv.error) as error:
        report['error'] = str(error)
        print(f'Check failed: {error}')
    finally:
        (output / 'overlap-diagnostics.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return {'screen_passed_needs_visual_review': 0, 'weak_connections': 3}.get(report['status'], 2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Horizontal capture ZIP or extracted capture folder')
    parser.add_argument('--output', required=True, help='New result folder; existing results are never overwritten')
    args = parser.parse_args()
    try:
        raise SystemExit(check(args.input, args.output))
    except (InputError, OSError, ValueError) as error:
        print(f'Cannot start check: {error}')
        raise SystemExit(2)
