"""Run a *local development* 360 viewer and Python upload processor.

Do NOT deploy this server to the internet. No account security or durable storage.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import socket
from threading import BoundedSemaphore
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from processor import MAX_INPUT_BYTES, PanoramaError, make_demo_panorama, process_panorama

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
UPLOADS = ROOT / "uploads"
UPLOAD_SLOT = BoundedSemaphore(1)
READ_TIMEOUT = 30
VENDOR_PREFIX = "/vendor/pannellum-2.5.7/"
VENDOR_FILES = {"pannellum.js", "pannellum.css", "COPYING", "VERSION"}


class Handler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(READ_TIMEOUT)

    def respond(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (ConnectionError, socket.timeout):
            pass  # The phone may disconnect while processing.

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/upload":
            return self.respond(404, {"error": "Not found"})
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Transfer-Encoding is not supported. Send a Content-Length."})
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
            return self.respond(411, {"error": "Content-Length required"})
        length = int(lengths[0])
        if not 0 < length <= MAX_INPUT_BYTES:
            return self.respond(413, {"error": "Choose an image between 1 byte and 25 MiB."})
        if not UPLOAD_SLOT.acquire(blocking=False):
            return self.respond(503, {"error": "Another image is processing. Please try again shortly."})
        try:
            try:
                data = self.rfile.read(length)
            except socket.timeout:
                return self.respond(408, {"error": "Upload timed out. Check Wi-Fi and try again."})
            except ConnectionError:
                return
            if len(data) != length:
                return self.respond(400, {"error": "Incomplete upload."})
            try:
                result = process_panorama(data, UPLOADS)
            except PanoramaError as exc:
                return self.respond(400, {"error": str(exc)})
            except OSError:
                return self.respond(500, {"error": "Cannot save the panorama. Check available disk space and uploads folder permissions."})
            self.respond(201, result.as_dict())
        finally:
            UPLOAD_SLOT.release()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/demo":
            if not self.allowed_file(UPLOADS / "demo.jpg", UPLOADS):
                return self.respond(404, {"error": "Test grid is missing. Restart the local server."})
            return self.respond(200, {"url": "/uploads/demo.jpg", "title": "Synthetic 360 test grid"})
        base = STATIC
        if path in {"/", "/index.html"}:
            filepath = STATIC / "index.html"
        elif path in {"/style.css", "/app.js", "/horizontal.html", "/horizontal.js", "/horizontal.css"}:
            filepath = STATIC / path.lstrip("/")
        elif path.startswith(VENDOR_PREFIX) and path[len(VENDOR_PREFIX):] in VENDOR_FILES:
            filepath = STATIC / path.lstrip("/")
        elif path.startswith("/uploads/"):
            filename = path.removeprefix("/uploads/")
            # Restrict to UUID-based outputs or the demo; refuse any traversal.
            if not re.fullmatch(r"(?:[0-9a-f]{32}|demo)\.jpg", filename):
                return self.respond(404, {"error": "Not found"})
            filepath = UPLOADS / filename
            base = UPLOADS
        else:
            return self.respond(404, {"error": "Not found"})

        if not self.allowed_file(filepath, base):
            return self.respond(404, {"error": "Not found"})
        try:
            stream = filepath.open("rb")
        except OSError:
            return self.respond(500, {"error": "Cannot read the requested local file."})
        mime = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
        # Explicit types avoid Windows registry MIME associations for scripts / CSS.
        mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".jpg": "image/jpeg"}.get(filepath.suffix, mime)
        with stream:
            import os
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(os.fstat(stream.fileno()).st_size))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while chunk := stream.read(1024 * 512):
                    self.wfile.write(chunk)
            except (ConnectionError, socket.timeout):
                pass

    @staticmethod
    def allowed_file(filepath: Path, base: Path) -> bool:
        # Resolve symlinks / Windows junctions as well as lexical traversal.
        try:
            resolved = filepath.resolve(strict=True)
            return resolved.is_relative_to(base.resolve()) and resolved.is_file()
        except (OSError, RuntimeError):
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="RentLease standalone mobile 360 panorama prototype")
    parser.add_argument("--lan", action="store_true", help="Allow other devices on the same trusted Wi-Fi network")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    make_demo_panorama(UPLOADS / "demo.jpg")
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    with ThreadingHTTPServer((host, args.port), Handler) as server:
        print(f"\nRentLease 360 Prototype running: http://127.0.0.1:{args.port}")
        if args.lan:
            print("Phone access: http://YOUR_COMPUTER_LAN_IP:%d (same trusted Wi-Fi)" % args.port)
            print("WARNING: local prototype has no authentication. Do not expose to the public internet.")
        print("Press Ctrl+C to stop. Files are stored locally under ./uploads\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping")

if __name__ == "__main__":
    main()
