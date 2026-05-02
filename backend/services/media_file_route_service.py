import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


GRID_TILE_MAX_AXIS = 10
GRID_TILE_MAX_COUNT = 100

IMAGE_EXTENSIONS = frozenset((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".avif"))
VIDEO_EXTENSIONS = frozenset((".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"))
AUDIO_EXTENSIONS = frozenset((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm"))
OUTPUT_INDEX_FILENAME = ".output_index.json"
OUTPUT_INDEX_VERSION = 1


class MediaFileRouteService:
    def __init__(
        self,
        *,
        directory,
        uploads_dir_getter,
        output_dir_getter,
        max_upload_bytes,
        next_output_filename,
        load_json_file,
        atomic_write_json,
        read_body,
        user_dir_getter=None,
        assets_dir_getter=None,
        ffprobe_getter=lambda: "ffprobe",
        image_derivative_display_max_edge=1280,
        image_derivative_thumb_max_edge=320,
        image_derivative_display_quality=78,
        image_derivative_thumb_quality=70,
        image_derivative_root_dirname="_derived",
    ):
        self.directory = os.path.abspath(directory)
        self._get_uploads_dir = uploads_dir_getter
        self._get_user_dir = user_dir_getter or (lambda: self.directory)
        self._get_assets_dir = assets_dir_getter or (lambda: os.path.join(self.directory, "data", "assets"))
        self._get_output_dir = output_dir_getter
        self.max_upload_bytes = int(max_upload_bytes or 0)
        self._next_output_filename = next_output_filename
        self._load_json_file = load_json_file
        self._atomic_write_json = atomic_write_json
        self._read_body = read_body
        self._get_ffprobe = ffprobe_getter
        self.image_derivative_display_max_edge = int(image_derivative_display_max_edge)
        self.image_derivative_thumb_max_edge = int(image_derivative_thumb_max_edge)
        self.image_derivative_display_quality = int(image_derivative_display_quality)
        self.image_derivative_thumb_quality = int(image_derivative_thumb_quality)
        self.image_derivative_root_dirname = str(image_derivative_root_dirname or "_derived")
        self._save_output_from_url_lock = threading.Lock()
        self._save_output_from_url_inflight = {}

    @staticmethod
    def _json_ok(data):
        return {"kind": "json_ok", "data": data}

    @staticmethod
    def _json_err(code, message):
        return {
            "kind": "json_err",
            "code": int(code),
            "message": str(message or ""),
        }

    @staticmethod
    def _parse_json_object(body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            return None, MediaFileRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, MediaFileRouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _normalize_posix_rel_path(path_value):
        return str(path_value or "").replace("\\", "/").strip("/")

    @classmethod
    def normalize_virtual_local_path(cls, path_value):
        raw = str(path_value or "").strip()
        if not raw:
            return ""
        slash_path = raw.replace("\\", "/")
        lower = slash_path.lower()
        if re.match(r"^[a-z][a-z0-9+.-]*:", lower):
            return ""
        if re.match(r"^[a-zA-Z]:/", slash_path) or slash_path.startswith("//"):
            return ""
        try:
            path_part = urllib.parse.urlsplit(slash_path).path
        except Exception:
            path_part = slash_path
        decoded = urllib.parse.unquote(path_part).strip().lstrip("/")
        parts = []
        for part in decoded.split("/"):
            segment = part.strip()
            if not segment or segment == ".":
                continue
            if segment == "..":
                return ""
            parts.append(segment)
        normalized = "/".join(parts)
        if normalized.startswith("output/"):
            return normalized
        if normalized.startswith("data/uploads/"):
            return normalized
        if normalized.startswith("data/assets/"):
            return normalized
        return ""

    @classmethod
    def _join_virtual_local_path(cls, root_prefix, rel_path):
        root = cls._normalize_posix_rel_path(root_prefix)
        rel = cls._normalize_posix_rel_path(rel_path)
        if root and rel:
            return f"{root}/{rel}"
        return root or rel

    @staticmethod
    def _is_path_inside(path, root):
        try:
            path_abs = os.path.abspath(path)
            root_abs = os.path.abspath(root)
            return os.path.commonpath([path_abs, root_abs]) == root_abs
        except Exception:
            return False

    @staticmethod
    def _safe_filename(filename):
        return re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(str(filename or "upload")))

    @staticmethod
    def _write_unique_upload_file(upload_dir, preferred_filename, file_bytes):
        safe_fn = MediaFileRouteService._safe_filename(preferred_filename or "upload") or "upload"
        stem, ext = os.path.splitext(safe_fn)
        stem = stem or "upload"
        stamp = int(time.time() * 1000)

        for attempt in range(1000):
            stored_fn = safe_fn if attempt == 0 else f"{stem}_{stamp}_{attempt:03d}{ext}"
            fpath = os.path.join(upload_dir, stored_fn)
            try:
                with open(fpath, "xb") as file:
                    file.write(file_bytes)
                return safe_fn, stored_fn, fpath
            except FileExistsError:
                continue

        raise RuntimeError("Unable to allocate unique upload filename")

    def _uploads_dir(self):
        return os.path.abspath(self._get_uploads_dir())

    def _output_dir(self):
        return os.path.abspath(self._get_output_dir())

    def _user_dir(self):
        return os.path.abspath(self._get_user_dir())

    def _assets_dir(self):
        return os.path.abspath(self._get_assets_dir())

    def _output_index_file(self):
        return os.path.join(self._user_dir(), OUTPUT_INDEX_FILENAME)

    def _ffprobe(self):
        return str(self._get_ffprobe() or "ffprobe")

    @staticmethod
    def _hash_dedupe_key(value):
        text = str(value or "").strip()
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_output_url_dedupe_map(self, index_data):
        root_index = self._ensure_output_index_root(index_data, self._output_dir())
        mapping = root_index.get("savedUrlOutputs")
        if not isinstance(mapping, dict):
            mapping = {}
            root_index["savedUrlOutputs"] = mapping
        return mapping

    def _lookup_saved_output_from_url(self, dedupe_hash):
        key = str(dedupe_hash or "").strip()
        if not key:
            return None
        index_data = self._load_output_index()
        mapping = self._get_output_url_dedupe_map(index_data)
        item = mapping.get(key)
        if not isinstance(item, dict):
            return None
        local_path = str(item.get("localPath") or item.get("path") or "").strip()
        abs_path = self.resolve_local_virtual_path(local_path)
        if (
            local_path.startswith("output/")
            and abs_path
            and self._is_path_inside(abs_path, self._output_dir())
            and os.path.isfile(abs_path)
        ):
            return local_path, abs_path
        try:
            mapping.pop(key, None)
            self._save_output_index(index_data)
        except Exception:
            pass
        return None

    def _remember_saved_output_from_url(self, dedupe_hash, local_path, url):
        key = str(dedupe_hash or "").strip()
        path = str(local_path or "").strip()
        if not key or not path.startswith("output/"):
            return
        index_data = self._load_output_index()
        mapping = self._get_output_url_dedupe_map(index_data)
        mapping[key] = {
            "localPath": path,
            "url": str(url or "").strip(),
            "savedAt": int(time.time() * 1000),
        }
        self._save_output_index(index_data)

    def _wait_for_save_output_from_url_owner(self, dedupe_hash):
        key = str(dedupe_hash or "").strip()
        if not key:
            return None
        while True:
            cached = self._lookup_saved_output_from_url(key)
            if cached:
                return cached
            with self._save_output_from_url_lock:
                event = self._save_output_from_url_inflight.get(key)
                if event is None:
                    event = threading.Event()
                    self._save_output_from_url_inflight[key] = event
                    return event
            event.wait()

    def _finish_save_output_from_url_owner(self, dedupe_hash, event):
        key = str(dedupe_hash or "").strip()
        if not key or event is None:
            return
        with self._save_output_from_url_lock:
            current = self._save_output_from_url_inflight.get(key)
            if current is event:
                self._save_output_from_url_inflight.pop(key, None)
                event.set()

    @classmethod
    def _classify_media_kind(cls, filename):
        ext = os.path.splitext(str(filename or "").lower())[1]
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        return "file"

    def resolve_virtual_media_root(self, local_path=None, abs_path=None):
        norm_local = self.normalize_virtual_local_path(local_path)
        if norm_local.startswith("output/"):
            rel = norm_local[len("output/") :].lstrip("/")
            return self._output_dir(), "output", rel
        if norm_local.startswith("data/uploads/"):
            rel = norm_local[len("data/uploads/") :].lstrip("/")
            return self._uploads_dir(), "data/uploads", rel
        if norm_local.startswith("data/assets/"):
            rel = norm_local[len("data/assets/") :].lstrip("/")
            return self._assets_dir(), "data/assets", rel

        abs_candidate = os.path.abspath(abs_path) if abs_path else None
        if abs_candidate and self._is_path_inside(abs_candidate, self._output_dir()):
            rel = os.path.relpath(abs_candidate, self._output_dir()).replace("\\", "/")
            return self._output_dir(), "output", rel
        if abs_candidate and self._is_path_inside(abs_candidate, self._uploads_dir()):
            rel = os.path.relpath(abs_candidate, self._uploads_dir()).replace("\\", "/")
            return self._uploads_dir(), "data/uploads", rel
        if abs_candidate and self._is_path_inside(abs_candidate, self._assets_dir()):
            rel = os.path.relpath(abs_candidate, self._assets_dir()).replace("\\", "/")
            return self._assets_dir(), "data/assets", rel
        return None, None, None

    def resolve_local_virtual_path(self, src_path):
        norm_slash = self.normalize_virtual_local_path(src_path)
        if not norm_slash:
            return None
        if norm_slash.startswith("output/"):
            rel = norm_slash[len("output/") :].lstrip("/")
            path = os.path.abspath(os.path.join(self._output_dir(), *rel.split("/")))
            return path if self._is_path_inside(path, self._output_dir()) else None
        if norm_slash.startswith("data/uploads/"):
            rel = norm_slash[len("data/uploads/") :].lstrip("/")
            path = os.path.abspath(os.path.join(self._uploads_dir(), *rel.split("/")))
            return path if self._is_path_inside(path, self._uploads_dir()) else None
        if norm_slash.startswith("data/assets/"):
            rel = norm_slash[len("data/assets/") :].lstrip("/")
            path = os.path.abspath(os.path.join(self._assets_dir(), *rel.split("/")))
            return path if self._is_path_inside(path, self._assets_dir()) else None
        return None

    @staticmethod
    def _image_variant_needs_alpha(img):
        try:
            if "A" in (img.getbands() or ()):
                return True
        except Exception:
            pass
        try:
            if img.mode == "P" and "transparency" in getattr(img, "info", {}):
                return True
        except Exception:
            pass
        return False

    def _build_image_derivative_target(self, root_abs, root_prefix, rel_original_path, variant, ext):
        normalized_rel = self._normalize_posix_rel_path(rel_original_path)
        rel_dir = self._normalize_posix_rel_path(os.path.dirname(normalized_rel))
        base_name = os.path.splitext(os.path.basename(normalized_rel))[0]
        rel_parts = [self.image_derivative_root_dirname, variant]
        if rel_dir:
            rel_parts.extend([p for p in rel_dir.split("/") if p])
        rel_parts.append(f"{base_name}.{variant}.{ext}")
        rel_variant = "/".join(rel_parts)
        abs_variant = os.path.abspath(os.path.join(root_abs, *rel_variant.split("/")))
        local_variant = self._join_virtual_local_path(root_prefix, rel_variant)
        return abs_variant, local_variant

    def _save_image_derivative_variant(self, source_img, out_path, max_edge, ext, quality, keep_alpha):
        from PIL import Image

        resampling = getattr(
            getattr(Image, "Resampling", Image),
            "LANCZOS",
            getattr(Image, "LANCZOS", Image.BICUBIC),
        )
        img = source_img.copy()
        img.thumbnail((max_edge, max_edge), resampling)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if keep_alpha:
            if img.mode not in ("RGBA", "LA"):
                img = img.convert("RGBA")
            if ext == "webp":
                img.save(out_path, format="WEBP", quality=quality, method=6)
                return
            img.save(out_path, format="PNG", optimize=True)
            return

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.mode == "L":
            img = img.convert("RGB")
        if ext == "jpg":
            img.save(
                out_path,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
            return
        img.save(out_path, format=ext.upper())

    def collect_image_derivative_payload(self, abs_path, root_abs, root_prefix, rel_original_path):
        try:
            from PIL import Image, ImageOps
        except Exception:
            return {}

        if not abs_path or not os.path.isfile(abs_path):
            return {}
        if not root_abs or not root_prefix or not rel_original_path:
            return {}
        if not self._is_path_inside(abs_path, root_abs):
            return {}

        try:
            with Image.open(abs_path) as opened:
                base_img = ImageOps.exif_transpose(opened)
                original_width, original_height = base_img.size
                if not (original_width > 0 and original_height > 0):
                    return {}
                keep_alpha = self._image_variant_needs_alpha(opened) or self._image_variant_needs_alpha(base_img)
                variant_ext = "png" if keep_alpha else "jpg"
                display_abs, display_local = self._build_image_derivative_target(
                    root_abs,
                    root_prefix,
                    rel_original_path,
                    "display",
                    variant_ext,
                )
                thumb_abs, thumb_local = self._build_image_derivative_target(
                    root_abs,
                    root_prefix,
                    rel_original_path,
                    "thumb",
                    variant_ext,
                )
                self._save_image_derivative_variant(
                    base_img,
                    display_abs,
                    self.image_derivative_display_max_edge,
                    variant_ext,
                    self.image_derivative_display_quality,
                    keep_alpha,
                )
                self._save_image_derivative_variant(
                    base_img,
                    thumb_abs,
                    self.image_derivative_thumb_max_edge,
                    variant_ext,
                    self.image_derivative_thumb_quality,
                    keep_alpha,
                )
        except Exception:
            return {}

        original_local = self._join_virtual_local_path(root_prefix, rel_original_path)
        return {
            "localPath": original_local,
            "originalLocalPath": original_local,
            "displayLocalPath": display_local,
            "thumbLocalPath": thumb_local,
            "originalWidth": int(original_width),
            "originalHeight": int(original_height),
        }

    def augment_saved_media_response(self, payload, abs_path, local_path):
        root_abs, root_prefix, rel_original_path = self.resolve_virtual_media_root(local_path, abs_path)
        if not root_abs or not root_prefix or not rel_original_path:
            return payload

        derivative_payload = self.collect_image_derivative_payload(
            abs_path,
            root_abs,
            root_prefix,
            rel_original_path,
        )
        if not derivative_payload:
            return payload

        next_payload = dict(payload or {})
        next_payload.update(derivative_payload)
        original_local = str(next_payload.get("originalLocalPath") or "").strip()
        display_local = str(next_payload.get("displayLocalPath") or "").strip()
        thumb_local = str(next_payload.get("thumbLocalPath") or "").strip()
        if original_local:
            next_payload["originalUrl"] = "/" + original_local.lstrip("/")
        if display_local:
            next_payload["displayUrl"] = "/" + display_local.lstrip("/")
        if thumb_local:
            next_payload["thumbUrl"] = "/" + thumb_local.lstrip("/")
        return next_payload

    def _handle_upload(self, handler):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
            content_type = handler.headers.get("Content-Type", "") or ""
            try:
                body = self._read_body(handler, self.max_upload_bytes)
            except ValueError as exc:
                if str(exc) == "REQUEST_BODY_TOO_LARGE":
                    return self._json_err(413, "Upload file too large")
                raise

            filename = (qs.get("filename", [""])[0] or "").strip()
            file_bytes = body

            if content_type.startswith("multipart/form-data") and b"\r\n" in body:
                match = re.search(r"boundary=([^;]+)", content_type)
                boundary = (match.group(1).strip().strip('"') if match else "")
                if boundary:
                    boundary_bytes = ("--" + boundary).encode("utf-8", "ignore")
                    parts = body.split(boundary_bytes)
                    for part in parts:
                        if b"Content-Disposition:" not in part:
                            continue
                        if b'name="file"' not in part and b"name='file'" not in part:
                            continue
                        header_end = part.find(b"\r\n\r\n")
                        if header_end == -1:
                            continue
                        header_blob = part[:header_end].decode("utf-8", "ignore")
                        data_blob = part[header_end + 4 :]
                        if data_blob.endswith(b"\r\n"):
                            data_blob = data_blob[:-2]
                        if data_blob.endswith(b"--"):
                            data_blob = data_blob[:-2]
                        if not filename:
                            mf = re.search(r'filename="([^"]+)"', header_blob)
                            if mf:
                                filename = mf.group(1).strip()
                        file_bytes = data_blob
                        break

            if len(file_bytes) > self.max_upload_bytes:
                return self._json_err(413, "Upload file too large")

            upload_dir = self._uploads_dir()
            os.makedirs(upload_dir, exist_ok=True)
            safe_fn, stored_fn, fpath = self._write_unique_upload_file(
                upload_dir,
                filename or "upload",
                file_bytes,
            )

            local_path = f"data/uploads/{stored_fn}"
            return self._json_ok(
                self.augment_saved_media_response(
                    {
                        "url": f"/{local_path}",
                        "localPath": local_path,
                        "filename": safe_fn,
                        "storedFilename": stored_fn,
                    },
                    fpath,
                    local_path,
                )
            )
        except Exception as exc:
            return self._json_err(500, f"Upload failed: {str(exc)}")

    def _handle_images_derivatives_ensure(self, handler):
        body = self._read_body(handler)
        data, error = self._parse_json_object(body)
        if error is not None:
            return error

        local_path = str(data.get("localPath") or data.get("path") or "").strip()
        if not local_path:
            return self._json_err(400, "Missing localPath")

        abs_path = self.resolve_local_virtual_path(local_path)
        if not abs_path or not os.path.isfile(abs_path):
            return self._json_err(404, "Image not found")

        root_abs, root_prefix, rel_original_path = self.resolve_virtual_media_root(local_path, abs_path)
        derivative_payload = self.collect_image_derivative_payload(
            abs_path,
            root_abs,
            root_prefix,
            rel_original_path,
        )
        if not derivative_payload:
            return self._json_err(400, "Derivative generation failed")

        response_payload = {
            "success": True,
            **derivative_payload,
        }
        response_payload["url"] = "/" + str(response_payload["localPath"]).lstrip("/")
        response_payload["originalUrl"] = "/" + str(response_payload["originalLocalPath"]).lstrip("/")
        response_payload["displayUrl"] = "/" + str(response_payload["displayLocalPath"]).lstrip("/")
        response_payload["thumbUrl"] = "/" + str(response_payload["thumbLocalPath"]).lstrip("/")
        return self._json_ok(response_payload)

    def _handle_save_output(self, handler):
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
            ext = (qs.get("ext", ["png"])[0] or "png").strip().lower()
            if not re.match(r"^[a-z0-9]{1,5}$", ext):
                ext = "png"

            sub_dir = (qs.get("subDir", [""])[0] or "").strip()
            kind = (qs.get("kind", [""])[0] or "").strip()
            if kind and not re.match(r"^[a-zA-Z0-9_-]+$", kind):
                kind = ""
            if sub_dir and re.match(r"^[a-zA-Z0-9 _-]+$", sub_dir):
                target_dir = os.path.join(self._output_dir(), sub_dir)
                os.makedirs(target_dir, exist_ok=True)
                filename = self._next_output_filename(ext)
                fpath = os.path.join(target_dir, filename)
                rel_path = f"output/{sub_dir}/{filename}"
            else:
                filename = self._next_output_filename(ext)
                fpath = os.path.join(self._output_dir(), filename)
                rel_path = f"output/{filename}"

            body = self._read_body(handler)
            if not body:
                return self._json_err(400, "Empty payload")

            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "wb") as file:
                file.write(body)

            if kind:
                meta_file = os.path.join(self._output_dir(), ".output_meta.json")
                meta = self._load_json_file(meta_file)
                if not isinstance(meta, dict):
                    meta = {}
                items = meta.get("items") if isinstance(meta.get("items"), list) else []
                items.append(
                    {
                        "kind": kind,
                        "localPath": rel_path,
                        "ts": int(time.time()),
                    }
                )
                if len(items) > 2000:
                    items = items[-2000:]
                meta["items"] = items
                try:
                    self._atomic_write_json(meta_file, meta)
                except Exception:
                    pass

            return self._json_ok(
                self.augment_saved_media_response(
                    {
                        "success": True,
                        "filename": filename,
                        "path": rel_path,
                        "localPath": rel_path,
                        "url": f"/{rel_path}",
                    },
                    fpath,
                    rel_path,
                )
            )
        except Exception as exc:
            return self._json_err(500, f"save_output failed: {str(exc)}")

    @staticmethod
    def _is_allowlisted_download_host(host):
        try:
            host_value = (host or "").strip().lower().strip(".")
        except Exception:
            return False
        if not host_value:
            return False
        if host_value in ("localhost", "127.0.0.1", "0.0.0.0"):
            return True
        if host_value == "runninghub.cn" or host_value.endswith(".runninghub.cn"):
            return True
        if host_value.endswith(".myqcloud.com") or host_value.endswith(".qcloud.com"):
            return True
        if host_value.endswith(".volces.com") or host_value.endswith(".aliyuncs.com") or host_value.endswith(".bcebos.com"):
            return True
        return False

    @staticmethod
    def _is_private_ip(ip_str):
        try:
            ip = ipaddress.ip_address(ip_str)
        except Exception:
            return True
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )

    @staticmethod
    def _extension_from_content_type(content_type):
        content_type = str(content_type or "").split(";", 1)[0].strip().lower()
        if content_type == "image/png":
            return "png"
        if content_type in ("image/jpeg", "image/jpg"):
            return "jpg"
        if content_type == "image/webp":
            return "webp"
        if content_type == "image/gif":
            return "gif"
        if content_type == "video/mp4":
            return "mp4"
        if content_type in ("video/webm", "audio/webm"):
            return "webm"
        return "bin"

    def _validate_download_host(self, parsed):
        host = parsed.hostname
        if not host:
            return self._json_err(400, "Invalid host")
        try:
            allow_private = self._is_allowlisted_download_host(host)
            if not allow_private:
                infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
                for info in infos:
                    ip_str = info[4][0]
                    if self._is_private_ip(ip_str):
                        return self._json_err(400, "Blocked private/reserved address")
        except Exception:
            return self._json_err(400, "DNS resolve failed")
        return None

    def _handle_save_output_from_url(self, handler):
        body = self._read_body(handler)
        data, error = self._parse_json_object(body)
        if error is not None:
            return error

        url = (data.get("url") or "").strip()
        if not url:
            return self._json_err(400, "Missing url")
        if url.startswith("//"):
            url = "https:" + url
        elif not re.match(r"^https?://", url, flags=re.I):
            url = "https://" + url.lstrip("/")
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return self._json_err(400, "Invalid url")
        if parsed.scheme not in ("http", "https"):
            return self._json_err(400, "Only http/https url allowed")

        host_error = self._validate_download_host(parsed)
        if host_error is not None:
            return host_error

        dedupe_hash = self._hash_dedupe_key(data.get("dedupeKey") or url)
        dedupe_owner = self._wait_for_save_output_from_url_owner(dedupe_hash)
        if isinstance(dedupe_owner, tuple):
            rel_path, cached_path = dedupe_owner
            filename = os.path.basename(cached_path)
            return self._json_ok(
                self.augment_saved_media_response(
                    {
                        "success": True,
                        "filename": filename,
                        "path": rel_path,
                        "localPath": rel_path,
                        "url": f"/{rel_path}",
                        "deduped": True,
                    },
                    cached_path,
                    rel_path,
                )
            )

        try:
            max_bytes = int(data.get("maxBytes") or 1024 * 1024 * 300)
        except Exception:
            max_bytes = 1024 * 1024 * 300

        try:
            request = urllib.request.Request(url, method="GET")
            request.add_header("User-Agent", "AI-Canvas/1.0")
            try:
                with urllib.request.urlopen(request, timeout=120) as resp:
                    content_type = resp.headers.get("Content-Type") or ""
                    ext = (data.get("ext") or "").strip().lower()
                    if not re.match(r"^[a-z0-9]{1,5}$", ext):
                        ext = ""
                    if not ext:
                        ext = self._extension_from_content_type(content_type)
                    filename = self._next_output_filename(ext)
                    fpath = os.path.join(self._output_dir(), filename)
                    total = 0
                    os.makedirs(os.path.dirname(fpath), exist_ok=True)
                    with open(fpath, "wb") as file:
                        while True:
                            chunk = resp.read(1024 * 256)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > max_bytes:
                                try:
                                    os.remove(fpath)
                                except Exception:
                                    pass
                                return self._json_err(413, "File too large")
                            file.write(chunk)
            except urllib.error.HTTPError as exc:
                return self._json_err(502, f"Download HTTPError: {exc.code}")
            except Exception as exc:
                return self._json_err(502, f"Download failed: {str(exc)}")

            rel_path = f"output/{filename}"
            self._remember_saved_output_from_url(dedupe_hash, rel_path, url)
            return self._json_ok(
                self.augment_saved_media_response(
                    {
                        "success": True,
                        "filename": filename,
                        "path": rel_path,
                        "localPath": rel_path,
                        "url": f"/{rel_path}",
                    },
                    fpath,
                    rel_path,
                )
            )
        finally:
            self._finish_save_output_from_url_owner(dedupe_hash, dedupe_owner)

    @staticmethod
    def _parse_grid_count(value):
        try:
            count = int(round(float(value)))
        except Exception:
            return 0
        if count < 1 or count > GRID_TILE_MAX_AXIS:
            return 0
        return count

    @staticmethod
    def _parse_image_quality(value, default=85):
        try:
            quality = int(round(float(value)))
        except Exception:
            return default
        return max(1, min(95, quality))

    @staticmethod
    def _normalize_output_image_ext(value):
        ext = str(value or "jpg").strip().lower()
        if ext == "jpeg":
            ext = "jpg"
        if ext not in ("jpg", "png", "webp"):
            ext = "jpg"
        return ext

    @staticmethod
    def _image_has_alpha(img):
        try:
            if "A" in (img.getbands() or ()):
                return True
        except Exception:
            pass
        try:
            return img.mode == "P" and "transparency" in getattr(img, "info", {})
        except Exception:
            return False

    def _prepare_grid_tile_for_save(self, tile, ext):
        from PIL import Image

        if ext in ("jpg", "webp"):
            if self._image_has_alpha(tile):
                flattened = Image.new("RGB", tile.size, (255, 255, 255))
                alpha_source = tile.convert("RGBA")
                flattened.paste(alpha_source, mask=alpha_source.getchannel("A"))
                return flattened
            if tile.mode not in ("RGB", "L"):
                return tile.convert("RGB")
            if tile.mode == "L":
                return tile.convert("RGB")
            return tile

        if ext == "png" and self._image_has_alpha(tile):
            return tile.convert("RGBA")
        if ext == "png" and tile.mode == "P":
            return tile.convert("RGBA")
        return tile

    def _save_grid_tile_image(self, tile, fpath, ext, quality):
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        prepared = self._prepare_grid_tile_for_save(tile, ext)
        if ext == "jpg":
            prepared.save(
                fpath,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
            return
        if ext == "webp":
            prepared.save(fpath, format="WEBP", quality=quality, method=6)
            return
        prepared.save(fpath, format="PNG", optimize=True)

    def _handle_grid_tiles_crop(self, handler):
        try:
            body = self._read_body(handler)
            data, error = self._parse_json_object(body)
            if error is not None:
                return error

            local_path = str(data.get("localPath") or data.get("path") or "").strip()
            if not local_path:
                return self._json_err(400, "Missing localPath")

            abs_path = self.resolve_local_virtual_path(local_path)
            if not abs_path or not os.path.isfile(abs_path):
                return self._json_err(404, "Image not found")

            root_abs, root_prefix, _ = self.resolve_virtual_media_root(local_path, abs_path)
            if root_prefix not in ("output", "data/uploads", "data/assets") or not self._is_path_inside(abs_path, root_abs):
                return self._json_err(403, "Image path is not allowed")

            cols = self._parse_grid_count(data.get("cols"))
            rows = self._parse_grid_count(data.get("rows"))
            if cols <= 0 or rows <= 0 or cols * rows > GRID_TILE_MAX_COUNT:
                return self._json_err(400, "Invalid grid size")

            ext = self._normalize_output_image_ext(data.get("ext"))
            quality = self._parse_image_quality(data.get("quality"), 85)
            sub_dir = str(data.get("subDir") or "").strip()
            if sub_dir and not re.match(r"^[a-zA-Z0-9 _-]+$", sub_dir):
                sub_dir = ""

            try:
                from PIL import Image, ImageOps
            except Exception:
                return self._json_err(500, "Pillow is required")

            target_dir = os.path.join(self._output_dir(), sub_dir) if sub_dir else self._output_dir()
            rel_dir = f"output/{sub_dir}" if sub_dir else "output"

            tiles = []
            with Image.open(abs_path) as opened:
                base_img = ImageOps.exif_transpose(opened)
                source_width, source_height = base_img.size
                tile_w = int(source_width // cols)
                tile_h = int(source_height // rows)
                if tile_w < 1 or tile_h < 1:
                    return self._json_err(400, "Grid tile is too small")

                for row in range(rows):
                    for col in range(cols):
                        crop_box = (
                            col * tile_w,
                            row * tile_h,
                            (col + 1) * tile_w,
                            (row + 1) * tile_h,
                        )
                        tile_img = base_img.crop(crop_box)
                        filename = self._next_output_filename(ext)
                        fpath = os.path.join(target_dir, filename)
                        rel_path = f"{rel_dir}/{filename}"
                        self._save_grid_tile_image(tile_img, fpath, ext, quality)
                        payload = self.augment_saved_media_response(
                            {
                                "success": True,
                                "filename": filename,
                                "path": rel_path,
                                "localPath": rel_path,
                                "url": f"/{rel_path}",
                                "row": row,
                                "col": col,
                                "w": tile_w,
                                "h": tile_h,
                                "width": tile_w,
                                "height": tile_h,
                            },
                            fpath,
                            rel_path,
                        )
                        tiles.append(payload)

            return self._json_ok(
                {
                    "success": True,
                    "cols": cols,
                    "rows": rows,
                    "tileWidth": tile_w,
                    "tileHeight": tile_h,
                    "sourceWidth": source_width,
                    "sourceHeight": source_height,
                    "tiles": tiles,
                }
            )
        except Exception as exc:
            return self._json_err(500, f"grid_tiles crop failed: {str(exc)}")

    def _resolve_output_list_dir(self, dir_value):
        rel = self._normalize_posix_rel_path(dir_value)
        norm = os.path.normpath(rel).replace("\\", "/")
        if norm in ("", "."):
            norm = ""
        if norm.startswith("../") or norm == ".." or "/../" in f"/{norm}/":
            return None, None
        output_dir = self._output_dir()
        abs_dir = os.path.abspath(os.path.join(output_dir, *([p for p in norm.split("/") if p] or [])))
        if not self._is_path_inside(abs_dir, output_dir):
            return None, None
        return abs_dir, norm

    def _handle_output_files_list(self, handler):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
        dir_value = qs.get("dir", [""])[0]
        order = str(qs.get("order", ["desc"])[0] or "desc").lower()
        if order not in ("asc", "desc"):
            order = "desc"

        abs_dir, rel_dir = self._resolve_output_list_dir(dir_value)
        if not abs_dir:
            return self._json_err(400, "Invalid output directory")
        if not os.path.isdir(abs_dir):
            return self._json_err(404, "Output directory not found")

        items = []
        try:
            names = os.listdir(abs_dir)
        except Exception as exc:
            return self._json_err(500, f"List output failed: {str(exc)}")

        output_root = os.path.abspath(self._output_dir())
        output_index = self._load_output_index()
        root_index = self._ensure_output_index_root(output_index, output_root)
        changed_index = False
        current_local_paths = set()

        for name in names:
            if not name or name.startswith("."):
                continue
            abs_path = os.path.abspath(os.path.join(abs_dir, name))
            if not self._is_path_inside(abs_path, self._output_dir()):
                continue
            rel_path = "/".join([p for p in (rel_dir, name) if p]).replace("\\", "/")
            local_path = self._join_virtual_local_path("output", rel_path)
            try:
                stat = os.stat(abs_path)
            except OSError:
                continue
            is_dir = os.path.isdir(abs_path)
            media_kind = "folder" if is_dir else self._classify_media_kind(name)
            size = 0 if is_dir else int(stat.st_size)
            mtime = int(stat.st_mtime * 1000)
            item = {
                "name": name,
                "kind": "directory" if is_dir else "file",
                "isDir": bool(is_dir),
                "dir": rel_path if is_dir else "",
                "relPath": rel_path,
                "localPath": local_path,
                "url": "" if is_dir else f"/{local_path}",
                "size": size,
                "mtime": mtime,
                "mediaKind": media_kind,
            }
            if not is_dir and media_kind in ("image", "video"):
                current_local_paths.add(local_path)
                cached = self._get_output_index_item(root_index, local_path, media_kind, size, mtime)
                if cached is None:
                    cached = self._build_output_index_item(abs_path, local_path, media_kind, size, mtime)
                    if cached is not None:
                        root_index["items"][local_path] = cached
                        changed_index = True
                if cached is not None:
                    item.update(self._output_index_item_to_media_payload(cached))
            items.append(item)

        changed_index = self._prune_output_index_for_directory(
            root_index,
            rel_dir,
            current_local_paths,
        ) or changed_index
        if changed_index:
            self._save_output_index(output_index)

        reverse = order == "desc"
        items.sort(
            key=lambda item: (
                0 if item["isDir"] else 1,
                -int(item["mtime"]) if reverse else int(item["mtime"]),
                str(item["name"]).lower(),
            )
        )

        parent = ""
        if rel_dir:
            parent = os.path.dirname(rel_dir).replace("\\", "/")
            if parent == ".":
                parent = ""
        parts = [part for part in rel_dir.split("/") if part]
        breadcrumbs = [{"name": "output", "dir": ""}]
        acc = []
        for part in parts:
            acc.append(part)
            breadcrumbs.append({"name": part, "dir": "/".join(acc)})

        return self._json_ok(
            {
                "success": True,
                "root": "output",
                "dir": rel_dir,
                "parent": parent,
                "order": order,
                "breadcrumbs": breadcrumbs,
                "items": items,
            }
        )

    def _resolve_output_file_delete_path(self, local_path):
        normalized = self._normalize_posix_rel_path(local_path)
        if not normalized.startswith("output/"):
            return "", ""
        rel = normalized[len("output/") :].lstrip("/")
        if not rel:
            return "", ""
        norm = os.path.normpath(rel).replace("\\", "/")
        if norm in ("", ".") or norm.startswith("../") or norm == ".." or "/../" in f"/{norm}/":
            return "", ""
        output_dir = self._output_dir()
        abs_path = os.path.abspath(os.path.join(output_dir, *[part for part in norm.split("/") if part]))
        if not self._is_path_inside(abs_path, output_dir):
            return "", ""
        return abs_path, self._join_virtual_local_path("output", norm)

    def _handle_output_files_delete(self, handler):
        data, error = self._parse_json_object(self._read_body(handler))
        if error is not None:
            return error
        raw_paths = data.get("localPaths")
        if not isinstance(raw_paths, list) or len(raw_paths) == 0:
            return self._json_err(400, "Missing localPaths")

        seen = set()
        targets = []
        for raw_path in raw_paths:
            abs_path, local_path = self._resolve_output_file_delete_path(raw_path)
            if not abs_path or not local_path:
                return self._json_err(400, "Invalid output file path")
            if local_path in seen:
                continue
            seen.add(local_path)
            if os.path.isdir(abs_path):
                return self._json_err(400, "Deleting folders is not allowed")
            targets.append((abs_path, local_path))

        deleted = []
        missing = []
        for abs_path, local_path in targets:
            if not os.path.exists(abs_path):
                missing.append(local_path)
                continue
            try:
                os.remove(abs_path)
                deleted.append(local_path)
            except IsADirectoryError:
                return self._json_err(400, "Deleting folders is not allowed")
            except Exception as exc:
                return self._json_err(500, f"Delete output file failed: {str(exc)}")

        output_index = self._load_output_index()
        root_index = self._ensure_output_index_root(output_index, self._output_dir())
        index_items = root_index.get("items")
        changed_index = False
        if isinstance(index_items, dict):
            for local_path in deleted:
                if local_path in index_items:
                    del index_items[local_path]
                    changed_index = True
        if changed_index:
            self._save_output_index(output_index)

        return self._json_ok(
            {
                "success": True,
                "deleted": deleted,
                "missing": missing,
            }
        )

    def _load_output_index(self):
        data = self._load_json_file(self._output_index_file())
        if not isinstance(data, dict):
            data = {}
        if data.get("version") != OUTPUT_INDEX_VERSION:
            return {"version": OUTPUT_INDEX_VERSION, "roots": {}}
        roots = data.get("roots")
        if not isinstance(roots, dict):
            data["roots"] = {}
        return data

    def _save_output_index(self, data):
        payload = data if isinstance(data, dict) else {}
        payload["version"] = OUTPUT_INDEX_VERSION
        if not isinstance(payload.get("roots"), dict):
            payload["roots"] = {}
        try:
            self._atomic_write_json(self._output_index_file(), payload)
        except Exception:
            pass

    def _ensure_output_index_root(self, index_data, output_root):
        roots = index_data.get("roots")
        if not isinstance(roots, dict):
            roots = {}
            index_data["roots"] = roots
        key = os.path.abspath(output_root)
        root_index = roots.get(key)
        if not isinstance(root_index, dict):
            root_index = {}
            roots[key] = root_index
        if not isinstance(root_index.get("items"), dict):
            root_index["items"] = {}
        root_index["outputRoot"] = key
        return root_index

    def _get_output_index_item(self, root_index, local_path, media_kind, size, mtime):
        items = root_index.get("items") if isinstance(root_index, dict) else {}
        cached = items.get(local_path) if isinstance(items, dict) else None
        if not isinstance(cached, dict):
            return None
        if str(cached.get("mediaKind") or "") != media_kind:
            return None
        if str(cached.get("localPath") or "") != local_path:
            return None
        if int(cached.get("size") or -1) != int(size):
            return None
        if int(cached.get("mtime") or -1) != int(mtime):
            return None
        return cached

    def _build_output_index_item(self, abs_path, local_path, media_kind, size, mtime):
        media_payload = self._read_output_media_dimensions(abs_path, media_kind)
        if not media_payload:
            return None
        item = {
            "mediaKind": media_kind,
            "localPath": local_path,
            "size": int(size),
            "mtime": int(mtime),
            "indexedAt": int(time.time() * 1000),
        }
        item.update(media_payload)
        return item

    @staticmethod
    def _output_index_item_to_media_payload(cached):
        payload = {}
        for key in (
            "width",
            "height",
            "originalWidth",
            "originalHeight",
            "videoWidth",
            "videoHeight",
            "duration",
            "thumbLocalPath",
            "displayLocalPath",
        ):
            if cached.get(key) not in (None, ""):
                payload[key] = cached.get(key)
        return payload

    def _prune_output_index_for_directory(self, root_index, rel_dir, current_local_paths):
        items = root_index.get("items")
        if not isinstance(items, dict):
            root_index["items"] = {}
            return True
        dir_prefix = self._join_virtual_local_path("output", rel_dir)
        dir_prefix = dir_prefix.rstrip("/")
        if dir_prefix:
            prefix = f"{dir_prefix}/"
        else:
            prefix = "output/"
        changed = False
        for local_path in list(items.keys()):
            if not str(local_path).startswith(prefix):
                continue
            rel = str(local_path)[len(prefix) :]
            if "/" in rel:
                continue
            if local_path not in current_local_paths:
                del items[local_path]
                changed = True
        return changed

    def _read_output_media_dimensions(self, abs_path, media_kind):
        if media_kind == "image":
            try:
                from PIL import Image, ImageOps

                with Image.open(abs_path) as opened:
                    img = ImageOps.exif_transpose(opened)
                    width, height = img.size
                if width > 0 and height > 0:
                    return {
                        "width": int(width),
                        "height": int(height),
                        "originalWidth": int(width),
                        "originalHeight": int(height),
                    }
            except Exception:
                return {}
        if media_kind == "video":
            try:
                startupinfo = None
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                proc = subprocess.run(
                    [
                        self._ffprobe(),
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "stream=width,height,duration",
                        "-of",
                        "json",
                        abs_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    startupinfo=startupinfo,
                )
                if proc.returncode != 0:
                    return {}
                data = json.loads(proc.stdout or "{}")
                streams = data.get("streams") if isinstance(data, dict) else []
                stream = streams[0] if isinstance(streams, list) and streams else {}
                width = int(float(stream.get("width") or 0))
                height = int(float(stream.get("height") or 0))
                duration = float(stream.get("duration") or 0)
                payload = {}
                if width > 0 and height > 0:
                    payload.update(
                        {
                            "width": width,
                            "height": height,
                            "videoWidth": width,
                            "videoHeight": height,
                        }
                    )
                if duration > 0:
                    payload["duration"] = duration
                return payload
            except Exception:
                return {}
        return {}

    def handle_get(self, handler, path):
        if path == "/api/v2/output-files":
            return self._handle_output_files_list(handler)

        return None

    def handle_post(self, handler, path):
        if path == "/api/upload":
            return self._handle_upload(handler)

        if path == "/api/v2/grid_tiles/crop":
            return self._handle_grid_tiles_crop(handler)

        if path == "/api/v2/images/derivatives/ensure":
            return self._handle_images_derivatives_ensure(handler)

        if path == "/api/v2/save_output":
            return self._handle_save_output(handler)

        if path == "/api/v2/save_output_from_url":
            return self._handle_save_output_from_url(handler)

        if path == "/api/v2/output-files/delete":
            return self._handle_output_files_delete(handler)

        return None
