import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request


GRID_TILE_MAX_AXIS = 10
GRID_TILE_MAX_COUNT = 100


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
        image_derivative_display_max_edge=1280,
        image_derivative_thumb_max_edge=320,
        image_derivative_display_quality=78,
        image_derivative_thumb_quality=70,
        image_derivative_root_dirname="_derived",
    ):
        self.directory = os.path.abspath(directory)
        self._get_uploads_dir = uploads_dir_getter
        self._get_output_dir = output_dir_getter
        self.max_upload_bytes = int(max_upload_bytes or 0)
        self._next_output_filename = next_output_filename
        self._load_json_file = load_json_file
        self._atomic_write_json = atomic_write_json
        self._read_body = read_body
        self.image_derivative_display_max_edge = int(image_derivative_display_max_edge)
        self.image_derivative_thumb_max_edge = int(image_derivative_thumb_max_edge)
        self.image_derivative_display_quality = int(image_derivative_display_quality)
        self.image_derivative_thumb_quality = int(image_derivative_thumb_quality)
        self.image_derivative_root_dirname = str(image_derivative_root_dirname or "_derived")

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

    def _uploads_dir(self):
        return os.path.abspath(self._get_uploads_dir())

    def _output_dir(self):
        return os.path.abspath(self._get_output_dir())

    def resolve_virtual_media_root(self, local_path=None, abs_path=None):
        norm_local = self._normalize_posix_rel_path(local_path)
        if norm_local.startswith("output/"):
            rel = norm_local[len("output/") :].lstrip("/")
            return self._output_dir(), "output", rel
        if norm_local.startswith("data/uploads/"):
            rel = norm_local[len("data/uploads/") :].lstrip("/")
            return self._uploads_dir(), "data/uploads", rel

        abs_candidate = os.path.abspath(abs_path) if abs_path else None
        if abs_candidate and self._is_path_inside(abs_candidate, self._output_dir()):
            rel = os.path.relpath(abs_candidate, self._output_dir()).replace("\\", "/")
            return self._output_dir(), "output", rel
        if abs_candidate and self._is_path_inside(abs_candidate, self._uploads_dir()):
            rel = os.path.relpath(abs_candidate, self._uploads_dir()).replace("\\", "/")
            return self._uploads_dir(), "data/uploads", rel
        return None, None, None

    def resolve_local_virtual_path(self, src_path):
        safe_src = str(src_path or "").strip().lstrip("/")
        norm_src = os.path.normpath(safe_src)
        if (
            not safe_src
            or norm_src.startswith("..")
            or norm_src.startswith("../")
            or norm_src.startswith("..\\")
        ):
            return None
        norm_slash = norm_src.replace("\\", "/")
        if norm_slash.startswith("output/"):
            rel = norm_slash[len("output/") :].lstrip("/")
            return os.path.abspath(os.path.join(self._output_dir(), rel))
        if norm_slash.startswith("data/uploads/"):
            rel = norm_slash[len("data/uploads/") :].lstrip("/")
            return os.path.abspath(os.path.join(self._uploads_dir(), rel))
        return os.path.abspath(os.path.join(self.directory, norm_src))

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

            safe_fn = self._safe_filename(filename or "upload")
            fpath = os.path.join(self._uploads_dir(), safe_fn)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "wb") as file:
                file.write(file_bytes)

            local_path = f"data/uploads/{safe_fn}"
            return self._json_ok(
                self.augment_saved_media_response(
                    {
                        "url": f"/{local_path}",
                        "localPath": local_path,
                        "filename": safe_fn,
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

        try:
            max_bytes = int(data.get("maxBytes") or 1024 * 1024 * 300)
        except Exception:
            max_bytes = 1024 * 1024 * 300

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
            from PIL import Image, ImageOps
        except Exception:
            return self._json_err(500, "Pillow is required")

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
            if root_prefix not in ("output", "data/uploads") or not self._is_path_inside(abs_path, root_abs):
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

        return None
