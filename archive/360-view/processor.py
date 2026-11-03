"""Local image validation/optimization; dimensions never identify projection or coverage."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import uuid
import warnings
from threading import Lock

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
TARGET_WIDTH = 4096
MIN_WIDTH = 1024
MIN_SHORT_SIDE = 256
MAX_DECODED_PIXELS = 40_000_000
SUPPORTED_FORMATS = ("JPEG", "PNG", "WEBP")
# Python versions without context-aware warning filters need serialized contexts.
_decode_lock = Lock()


class PanoramaError(ValueError):
    """User-facing invalid image / processing failure."""


@dataclass(frozen=True)
class PanoramaResult:
    filename: str
    width: int
    height: int
    source_bytes: int
    output_bytes: int
    jpeg_quality: int

    def as_dict(self) -> dict:
        return {
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "source_bytes": self.source_bytes,
            "output_bytes": self.output_bytes,
            "jpeg_quality": self.jpeg_quality,
            "url": f"/uploads/{self.filename}",
        }


def _check_dimensions(width: int, height: int) -> None:
    if width * height > MAX_DECODED_PIXELS:
        raise PanoramaError("Image exceeds the 40 million decoded pixel limit. Export a smaller panorama.")
    if max(width, height) < MIN_WIDTH or min(width, height) < MIN_SHORT_SIDE:
        raise PanoramaError("Image is too small. Use at least 1024 pixels on the long side and 256 on the short side.")


def _decode(data: bytes) -> Image.Image:
    with _decode_lock, warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        warnings.simplefilter("error", UserWarning)
        try:
            with Image.open(BytesIO(data), formats=SUPPORTED_FORMATS) as opened:
                # Enforce a hard cap before verify/load/transpose/convert allocate pixels.
                width, height = opened.size
                if width * height > MAX_DECODED_PIXELS:
                    raise PanoramaError("Image exceeds the 40 million decoded pixel limit. Export a smaller panorama.")
                if getattr(opened, "n_frames", 1) != 1 or getattr(opened, "is_animated", False):
                    raise PanoramaError("Animated or multi-frame images are not supported. Export a single still image.")
                # PNG getexif() can itself trigger load(). Check both possible
                # orientations now, and the actual oriented dimensions after decode.
                _check_dimensions(max(width, height), min(width, height))
                opened.verify()
            # verify() invalidates the decoder; reopen and force complete decoding.
            with Image.open(BytesIO(data), formats=SUPPORTED_FORMATS) as opened:
                opened.load()
                with ImageOps.exif_transpose(opened) as oriented:
                    _check_dimensions(*oriented.size)
                    # A new pixel-only canvas strips EXIF/GPS, XMP, ICC and comments.
                    clean = Image.new("RGB", oriented.size, "white")
                    if oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info:
                        with oriented.convert("RGBA") as rgba:
                            clean.paste(rgba, mask=rgba.getchannel("A"))
                    else:
                        with oriented.convert("RGB") as rgb:
                            clean.paste(rgb)
                    return clean
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise PanoramaError("Image exceeds the safe decoded pixel limit. Export a smaller panorama.") from exc
        except PanoramaError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError,
                OverflowError, TypeError, UserWarning, MemoryError) as exc:
            raise PanoramaError("Cannot decode this image. Use an intact, still JPEG, PNG, or WebP file.") from exc


def process_panorama(data: bytes, upload_dir: Path, max_width: int = TARGET_WIDTH) -> PanoramaResult:
    """Validate and compress a panorama; save a random-name, metadata-free JPEG."""
    if not data:
        raise PanoramaError("The uploaded file is empty.")
    if len(data) > MAX_INPUT_BYTES:
        raise PanoramaError("The original image exceeds the 25 MiB prototype upload limit.")
    if not isinstance(max_width, int) or not MIN_WIDTH <= max_width <= TARGET_WIDTH or max_width % 2:
        raise PanoramaError("The configured maximum width must be even and between 1024 and 4096 pixels.")

    image = _decode(data)
    try:
        width, height = image.size
        if max(width, height) > max_width:
            scale = max_width / max(width, height)
            resized = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS)
            image.close()
            image = resized
        new_width, new_height = image.size
        encoded = None
        selected_quality = None
        for quality in (86, 80, 74, 66, 58, 50):
            out = BytesIO()
            image.save(out, format="JPEG", quality=quality, optimize=True, progressive=True, subsampling=0)
            candidate = out.getvalue()
            if len(candidate) < MAX_OUTPUT_BYTES:
                encoded, selected_quality = candidate, quality
                break
        if encoded is None:
            raise PanoramaError("Unable to compress below 10 MiB. Use a smaller source panorama.")
    except (OSError, MemoryError) as exc:
        raise PanoramaError("Cannot optimize this image. Export a smaller panorama and try again.") from exc
    finally:
        image.close()

    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    destination = upload_dir / filename
    temporary = destination.with_suffix(".tmp")
    try:
        with temporary.open("xb") as output:
            output.write(encoded)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return PanoramaResult(filename, new_width, new_height, len(data), len(encoded), selected_quality)


def make_demo_panorama(path: Path) -> None:
    """Create a synthetic 2:1 equirectangular test pattern, NOT a photo of a room."""
    if path.exists():
        return
    width, height = 2048, 1024
    im = Image.new("RGB", (width, height), "#a4d4eb")
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, height // 2, width, height), fill="#e3c99c")
    for x in range(0, width, 128):
        draw.line((x, 0, x, height), fill="#365f7a", width=2)
    for y in range(0, height, 128):
        draw.line((0, y, width, y), fill="#365f7a", width=2)
    for idx, x in enumerate((0, 512, 1024, 1536)):
        draw.rectangle((x+15, 458, x+400, 555), fill="#173449")
        draw.text((x+35, 490), f"TEST VIEW {idx*90} deg", fill="white")
    draw.text((45, 45), "SYNTHETIC 360 TEST GRID - NOT A REAL ROOM", fill="#102f48")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=88)
