import base64
import hashlib
import io
import os
import threading
import time
from collections import OrderedDict


class Sam3Service:
    def __init__(
        self,
        *,
        directory,
        assets_dir,
        uploads_dir_provider,
        output_dir_provider,
        path_inside_checker,
    ):
        self.directory = os.path.abspath(directory)
        self.assets_dir = os.path.abspath(assets_dir)
        self._get_uploads_dir = uploads_dir_provider
        self._get_output_dir = output_dir_provider
        self._is_path_inside = path_inside_checker
        self.onnx_dir = os.path.join(self.directory, "models", "sam3_onnx")
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._sessions = None
        self._tokenizer = None
        self._lang_cache_lock = threading.Lock()
        self._lang_cache = {}
        self._image_cache_lock = threading.Lock()
        self._image_cache = OrderedDict()
        self._image_cache_max = 6
        self._last_use_lock = threading.Lock()
        self._last_use_ts = 0.0

    def enabled(self):
        try:
            value = (os.environ.get("SAM3_ENABLED", "0") or "0").strip().lower()
            return value in ("1", "true", "yes", "on")
        except Exception:
            return False

    def touch(self):
        try:
            now = time.time()
        except Exception:
            now = 0.0
        with self._last_use_lock:
            self._last_use_ts = now

    def get_idle_sec(self):
        with self._last_use_lock:
            ts = float(self._last_use_ts or 0.0)
        try:
            now = time.time()
        except Exception:
            now = ts
        if ts <= 0:
            return None
        return max(0.0, now - ts)

    def clear_caches(self):
        with self._lang_cache_lock:
            self._lang_cache.clear()
        with self._image_cache_lock:
            self._image_cache.clear()

    def unload(self):
        with self._lock:
            sessions = self._sessions
            self._sessions = None
            self._tokenizer = None
        with self._last_use_lock:
            self._last_use_ts = 0.0
        self.clear_caches()
        try:
            import gc

            del sessions
            gc.collect()
        except Exception:
            pass

    @staticmethod
    def get_np():
        import numpy as np

        return np

    @staticmethod
    def get_pil_image():
        from PIL import Image

        return Image

    @staticmethod
    def get_ort():
        import onnxruntime as ort

        return ort

    @staticmethod
    def has_tensorrt_runtime():
        try:
            path_env = os.environ.get("PATH", "") or ""
            for part in [p for p in path_env.split(os.pathsep) if p]:
                directory = part.strip().strip('"')
                if not directory:
                    continue
                if os.path.isfile(os.path.join(directory, "nvinfer_10.dll")):
                    return True
                try:
                    for filename in os.listdir(directory):
                        lower = filename.lower()
                        if lower.startswith("nvinfer_") and lower.endswith(".dll"):
                            if os.path.isfile(os.path.join(directory, filename)):
                                return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    def get_tokenizer(self):
        if self._tokenizer is not None:
            return self._tokenizer
        os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        from transformers import CLIPTokenizerFast

        local_dir = os.path.join(self.onnx_dir, "clip_tokenizer")
        if os.path.isdir(local_dir):
            self._tokenizer = CLIPTokenizerFast.from_pretrained(
                local_dir,
                local_files_only=True,
            )
        else:
            self._tokenizer = CLIPTokenizerFast.from_pretrained(
                "openai/clip-vit-large-patch14"
            )
        return self._tokenizer

    def _fallback_providers(self, ort):
        try:
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "CoreMLExecutionProvider" in available:
                return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
            if "DmlExecutionProvider" in available:
                return ["DmlExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        return ["CPUExecutionProvider"]

    def load_sessions(self):
        if not self.enabled():
            raise RuntimeError("SAM3 disabled")
        if self._sessions is not None:
            return self._sessions
        with self._lock:
            if self._sessions is not None:
                return self._sessions
            ort = self.get_ort()
            encoder_path = os.path.join(self.onnx_dir, "sam3_image_encoder.onnx")
            language_path = os.path.join(self.onnx_dir, "sam3_language_encoder.onnx")
            decoder_path = os.path.join(self.onnx_dir, "sam3_decoder.onnx")
            missing = []
            if not os.path.exists(encoder_path):
                missing.append("sam3_image_encoder.onnx")
            if not os.path.exists(language_path):
                missing.append("sam3_language_encoder.onnx")
            if not os.path.exists(decoder_path):
                missing.append("sam3_decoder.onnx")
            if missing:
                raise RuntimeError("Missing model files: " + ", ".join(missing))

            providers = []
            try:
                available = ort.get_available_providers()
                use_trt = (os.environ.get("SAM3_ENABLE_TRT", "0") or "0").strip() in (
                    "1",
                    "true",
                    "True",
                    "YES",
                    "yes",
                )
                if (
                    use_trt
                    and "TensorrtExecutionProvider" in available
                    and self.has_tensorrt_runtime()
                ):
                    cache_dir = os.path.join(
                        os.path.abspath(self._get_output_dir()),
                        "sam3_trt_cache",
                    )
                    try:
                        os.makedirs(cache_dir, exist_ok=True)
                    except Exception:
                        pass
                    trt_opts = {
                        "trt_engine_cache_enable": True,
                        "trt_engine_cache_path": cache_dir,
                        "trt_fp16_enable": True,
                    }
                    providers = [
                        ("TensorrtExecutionProvider", trt_opts),
                        "CUDAExecutionProvider",
                        "CPUExecutionProvider",
                    ]
                elif "CUDAExecutionProvider" in available:
                    try:
                        mem_gb = float(
                            os.environ.get("SAM3_CUDA_MEM_LIMIT_GB", "12") or "12"
                        )
                    except Exception:
                        mem_gb = 12.0
                    mem_limit = int(mem_gb * 1024 * 1024 * 1024) if mem_gb > 0 else 0
                    cuda_opts = {
                        "arena_extend_strategy": "kSameAsRequested",
                        "cudnn_conv_algo_search": "DEFAULT",
                        "gpu_mem_limit": mem_limit,
                    }
                    providers = [
                        ("CUDAExecutionProvider", cuda_opts),
                        "CPUExecutionProvider",
                    ]
                elif "CoreMLExecutionProvider" in available:
                    providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
                elif "DmlExecutionProvider" in available:
                    providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                else:
                    providers = ["CPUExecutionProvider"]
            except Exception:
                providers = ["CPUExecutionProvider"]

            session_options = ort.SessionOptions()
            try:
                threads = int(os.environ.get("SAM3_ORT_THREADS", "0") or "0")
            except Exception:
                threads = 0
            cpu_count = int(os.cpu_count() or 4)
            threads = threads if threads > 0 else max(2, cpu_count // 2)
            if threads > 8:
                threads = 8
            session_options.intra_op_num_threads = max(1, threads)
            try:
                session_options.inter_op_num_threads = 1
            except Exception:
                pass
            try:
                session_options.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
            except Exception:
                pass
            try:
                session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            except Exception:
                pass

            try:
                session_image = ort.InferenceSession(
                    encoder_path,
                    sess_options=session_options,
                    providers=providers,
                )
                session_language = ort.InferenceSession(
                    language_path,
                    sess_options=session_options,
                    providers=providers,
                )
                session_decode = ort.InferenceSession(
                    decoder_path,
                    sess_options=session_options,
                    providers=providers,
                )
            except Exception as exc:
                message = str(exc)
                if (
                    "TensorrtExecutionProvider" in message
                    or "TensorRT" in message
                    or "nvinfer" in message
                ):
                    fallback = self._fallback_providers(ort)
                    session_image = ort.InferenceSession(
                        encoder_path,
                        sess_options=session_options,
                        providers=fallback,
                    )
                    session_language = ort.InferenceSession(
                        language_path,
                        sess_options=session_options,
                        providers=fallback,
                    )
                    session_decode = ort.InferenceSession(
                        decoder_path,
                        sess_options=session_options,
                        providers=fallback,
                    )
                else:
                    raise
            self._sessions = {
                "image": session_image,
                "language": session_language,
                "decode": session_decode,
            }
            return self._sessions

    def safe_resolve_image_path(self, path_value):
        if not isinstance(path_value, str):
            return None
        value = path_value.strip().lstrip("/")
        if not value:
            return None
        uploads_dir = os.path.abspath(self._get_uploads_dir())
        output_dir = os.path.abspath(self._get_output_dir())
        if value.startswith("data/uploads/"):
            rel = value[len("data/uploads/") :].lstrip("/\\")
            abs_path = os.path.abspath(os.path.join(uploads_dir, rel))
            if self._is_path_inside(abs_path, uploads_dir) and os.path.isfile(abs_path):
                return abs_path
        if value.startswith("output/"):
            rel = value[len("output/") :].lstrip("/\\")
            abs_path = os.path.abspath(os.path.join(output_dir, rel))
            if self._is_path_inside(abs_path, output_dir) and os.path.isfile(abs_path):
                return abs_path
        if value.startswith("data/assets/"):
            abs_path = os.path.abspath(os.path.join(self.directory, value))
            if self._is_path_inside(abs_path, self.assets_dir) and os.path.isfile(abs_path):
                return abs_path
        return None

    def get_language_features(self, prompt=None):
        np = self.get_np()
        sessions = self.load_sessions()
        prompt_text = (prompt or "visual").strip() or "visual"
        with self._lang_cache_lock:
            cached = self._lang_cache.get(prompt_text)
        if cached is not None:
            return cached
        tokenizer = self.get_tokenizer()
        token_ids = tokenizer(
            [prompt_text],
            padding="max_length",
            max_length=32,
            truncation=True,
            return_tensors="np",
        )["input_ids"]
        token_ids = np.asarray(token_ids, dtype=np.int64)
        outputs = sessions["language"].run(
            None,
            {sessions["language"].get_inputs()[0].name: token_ids},
        )
        language_mask = outputs[0]
        language_features = outputs[1]
        with self._lang_cache_lock:
            self._lang_cache[prompt_text] = (language_mask, language_features)
        return language_mask, language_features

    def get_image_embedding(self, *, abs_path=None, b64_data=None):
        np = self.get_np()
        Image = self.get_pil_image()
        sessions = self.load_sessions()

        raw_bytes = None
        image_cache_key = None
        if b64_data:
            encoded = b64_data.split(",", 1)[1] if isinstance(b64_data, str) and "," in b64_data else b64_data
            raw_bytes = base64.b64decode(encoded)
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        else:
            image = Image.open(abs_path).convert("RGB")

        orig_w, orig_h = image.size
        if abs_path:
            try:
                stat = os.stat(abs_path)
                image_cache_key = (
                    f"p|{os.path.abspath(abs_path)}|"
                    f"{int(stat.st_mtime_ns)}|{int(stat.st_size)}"
                )
            except Exception:
                image_cache_key = f"p|{os.path.abspath(abs_path)}"
        else:
            try:
                digest = hashlib.md5(raw_bytes or b"").hexdigest()
                image_cache_key = f"b|{digest}|{len(raw_bytes or b'')}"
            except Exception:
                image_cache_key = "b|0"

        enc_out = None
        if image_cache_key:
            with self._image_cache_lock:
                enc_out = self._image_cache.get(image_cache_key)
                if enc_out is not None:
                    self._image_cache.move_to_end(image_cache_key, last=True)

        if enc_out is None:
            image_resized = image.resize((1008, 1008))
            chw = np.asarray(image_resized, dtype=np.uint8).transpose(2, 0, 1)
            input_name = sessions["image"].get_inputs()[0].name
            output_values = sessions["image"].run(None, {input_name: chw})
            output_names = [item.name for item in sessions["image"].get_outputs()]
            output_map = {key: value for key, value in zip(output_names, output_values)}
            keep_keys = (
                "backbone_fpn_0",
                "backbone_fpn_1",
                "backbone_fpn_2",
                "vision_pos_enc_2",
            )
            enc_out = {key: output_map[key] for key in keep_keys if key in output_map}
            if image_cache_key and enc_out:
                with self._image_cache_lock:
                    self._image_cache[image_cache_key] = enc_out
                    self._image_cache.move_to_end(image_cache_key, last=True)
                    while len(self._image_cache) > self._image_cache_max:
                        self._image_cache.popitem(last=False)

        return enc_out or {}, orig_w, orig_h

    def run_segment(
        self,
        *,
        abs_path=None,
        b64_data=None,
        points=None,
        prompt=None,
        single_point_box_px=None,
        multi_point_pad_ratio=None,
    ):
        np = self.get_np()
        sessions = self.load_sessions()
        enc_out, orig_w, orig_h = self.get_image_embedding(
            abs_path=abs_path,
            b64_data=b64_data,
        )
        language_mask, language_features = self.get_language_features(prompt=prompt)

        fg = []
        bg = []
        for point in points or []:
            try:
                x = float(point.get("x"))
                y = float(point.get("y"))
                label = int(point.get("label"))
            except Exception:
                continue
            if label == 1:
                fg.append((x, y))
            else:
                bg.append((x, y))

        if not fg:
            raise RuntimeError("Missing foreground point")

        def clamp(value, low, high):
            return low if value < low else (high if value > high else value)

        fg_points = []
        for x, y in fg:
            xx = clamp(float(x), 0.0, float(max(0, orig_w - 1)))
            yy = clamp(float(y), 0.0, float(max(0, orig_h - 1)))
            fg_points.append((xx, yy))

        if len(fg_points) == 1:
            try:
                box_px = float(single_point_box_px) if single_point_box_px is not None else 160.0
            except Exception:
                box_px = 160.0
            box_px = 32.0 if box_px < 32.0 else (2048.0 if box_px > 2048.0 else box_px)
            x, y = fg_points[0]
            cx = clamp(x / float(orig_w), 0.0, 1.0)
            cy = clamp(y / float(orig_h), 0.0, 1.0)
            bw = clamp(box_px / float(orig_w), 0.02, 0.98)
            bh = clamp(box_px / float(orig_h), 0.02, 0.98)
        else:
            xs = [item[0] for item in fg_points]
            ys = [item[1] for item in fg_points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            span = max(max_x - min_x, max_y - min_y)
            try:
                pad_ratio = (
                    float(multi_point_pad_ratio)
                    if multi_point_pad_ratio is not None
                    else 0.35
                )
            except Exception:
                pad_ratio = 0.35
            pad_ratio = 0.05 if pad_ratio < 0.05 else (1.2 if pad_ratio > 1.2 else pad_ratio)
            pad = max(24.0, span * pad_ratio)
            x0 = clamp(min_x - pad, 0.0, float(orig_w))
            x1 = clamp(max_x + pad, 0.0, float(orig_w))
            y0 = clamp(min_y - pad, 0.0, float(orig_h))
            y1 = clamp(max_y + pad, 0.0, float(orig_h))
            if x1 - x0 < 2.0:
                cx0 = (min_x + max_x) * 0.5
                x0 = clamp(cx0 - 1.0, 0.0, float(orig_w))
                x1 = clamp(cx0 + 1.0, 0.0, float(orig_w))
            if y1 - y0 < 2.0:
                cy0 = (min_y + max_y) * 0.5
                y0 = clamp(cy0 - 1.0, 0.0, float(orig_h))
                y1 = clamp(cy0 + 1.0, 0.0, float(orig_h))
            bw = clamp((x1 - x0) / float(orig_w), 0.02, 0.98)
            bh = clamp((y1 - y0) / float(orig_h), 0.02, 0.98)
            cx = clamp(((x0 + x1) * 0.5) / float(orig_w), 0.0, 1.0)
            cy = clamp(((y0 + y1) * 0.5) / float(orig_h), 0.0, 1.0)

        box_coords = np.array([[[cx, cy, bw, bh]]], dtype=np.float32)
        box_labels = np.array([[1]], dtype=np.int64)
        box_masks = np.array([[False]], dtype=np.bool_)
        feeds = {
            "original_height": np.array(orig_h, dtype=np.int64),
            "original_width": np.array(orig_w, dtype=np.int64),
            "language_mask": language_mask,
            "language_features": language_features,
            "box_coords": box_coords,
            "box_labels": box_labels,
            "box_masks": box_masks,
        }
        for key in (
            "backbone_fpn_0",
            "backbone_fpn_1",
            "backbone_fpn_2",
            "vision_pos_enc_2",
        ):
            if key in enc_out:
                feeds[key] = enc_out[key]
        output_values = sessions["decode"].run(None, feeds)
        masks = output_values[-1]
        mask_array = np.asarray(masks)
        if mask_array.size == 0:
            empty_mask = np.zeros((1008, 1008), dtype=np.uint8)
            return empty_mask, 1008, 1008
        if mask_array.ndim == 4 and mask_array.shape[1] == 1:
            mask_array = mask_array[:, 0, :, :]
        if mask_array.ndim == 4 and mask_array.shape[0] == 1:
            mask_array = mask_array[0]
        if mask_array.ndim == 3:
            mask_array = mask_array[0]
        if mask_array.dtype != np.bool_:
            mask_array = mask_array > 0
        mask_u8 = mask_array.astype(np.uint8) * 255
        if bg:
            mask_h = int(mask_u8.shape[0])
            mask_w = int(mask_u8.shape[1])
            radius = int(max(2, min(mask_w, mask_h) * 0.02))
            yy, xx = np.ogrid[:mask_h, :mask_w]
            for bx, by in bg:
                try:
                    mx = int(round(float(bx) / float(orig_w) * float(mask_w)))
                    my = int(round(float(by) / float(orig_h) * float(mask_h)))
                except Exception:
                    continue
                if mx < 0:
                    mx = 0
                elif mx > mask_w - 1:
                    mx = mask_w - 1
                if my < 0:
                    my = 0
                elif my > mask_h - 1:
                    my = mask_h - 1
                dist2 = (xx - mx) ** 2 + (yy - my) ** 2
                mask_u8[dist2 <= radius * radius] = 0
        return mask_u8, int(mask_u8.shape[1]), int(mask_u8.shape[0])

    def _resolve_segment_source(self, image_local_path, image_base64):
        if image_base64:
            return None
        abs_path = self.safe_resolve_image_path(image_local_path)
        if not abs_path:
            raise ValueError("Invalid imageLocalPath or imageBase64")
        return abs_path

    def build_info(self):
        info = {
            "success": True,
            "ortProviders": [],
            "ortVersion": "",
            "sam3EnableTrt": False,
            "tensorrtRuntimeFound": False,
            "sam3IdleSec": None,
            "sam3IdleUnloadSec": None,
            "sam3Enabled": False,
            "sam3SessionsLoaded": False,
            "sessions": None,
        }
        try:
            info["sam3Enabled"] = self.enabled()
        except Exception:
            info["sam3Enabled"] = False
        try:
            info["sam3EnableTrt"] = (os.environ.get("SAM3_ENABLE_TRT", "0") or "0").strip() in (
                "1",
                "true",
                "True",
                "YES",
                "yes",
            )
        except Exception:
            info["sam3EnableTrt"] = False
        try:
            info["tensorrtRuntimeFound"] = self.has_tensorrt_runtime()
        except Exception:
            info["tensorrtRuntimeFound"] = False
        try:
            ort = self.get_ort()
            info["ortVersion"] = getattr(ort, "__version__", "") or ""
            try:
                info["ortProviders"] = ort.get_available_providers()
            except Exception:
                info["ortProviders"] = []
        except Exception:
            pass
        try:
            try:
                unload_sec = float(os.environ.get("SAM3_IDLE_UNLOAD_SEC", "300") or "300")
            except Exception:
                unload_sec = 300.0
            info["sam3IdleUnloadSec"] = unload_sec
            info["sam3IdleSec"] = self.get_idle_sec()
        except Exception:
            pass
        try:
            info["sam3SessionsLoaded"] = self._sessions is not None
        except Exception:
            info["sam3SessionsLoaded"] = False
        if info.get("sam3Enabled") and info.get("sam3SessionsLoaded"):
            try:
                sessions = self._sessions
                info["sessions"] = {
                    "image": sessions["image"].get_providers()
                    if sessions and sessions.get("image")
                    else [],
                    "language": sessions["language"].get_providers()
                    if sessions and sessions.get("language")
                    else [],
                    "decode": sessions["decode"].get_providers()
                    if sessions and sessions.get("decode")
                    else [],
                }
            except Exception as exc:
                info["success"] = False
                info["error"] = str(exc)
        return info

    def segment_png(
        self,
        *,
        image_local_path="",
        image_base64="",
        points=None,
        prompt="visual",
        single_point_box_px=None,
        multi_point_pad_ratio=None,
    ):
        self.touch()
        abs_path = self._resolve_segment_source(image_local_path, image_base64)
        with self._infer_lock:
            mask_u8, mask_w, mask_h = self.run_segment(
                abs_path=abs_path,
                b64_data=image_base64,
                points=points,
                prompt=prompt,
                single_point_box_px=single_point_box_px,
                multi_point_pad_ratio=multi_point_pad_ratio,
            )
        Image = self.get_pil_image()
        image = Image.fromarray(mask_u8, mode="L")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return {
            "success": True,
            "maskPngBase64": base64.b64encode(buffer.getvalue()).decode("ascii"),
            "maskWidth": mask_w,
            "maskHeight": mask_h,
        }

    def segment_raw(
        self,
        *,
        image_local_path="",
        image_base64="",
        points=None,
        prompt="visual",
    ):
        self.touch()
        abs_path = self._resolve_segment_source(image_local_path, image_base64)
        with self._infer_lock:
            mask_u8, mask_w, mask_h = self.run_segment(
                abs_path=abs_path,
                b64_data=image_base64,
                points=points,
                prompt=prompt,
            )
        return {
            "body": bytes(mask_u8.tobytes()),
            "maskWidth": mask_w,
            "maskHeight": mask_h,
        }

    def prepare(
        self,
        *,
        image_local_path="",
        image_base64="",
        prompt="visual",
    ):
        self.touch()
        abs_path = self._resolve_segment_source(image_local_path, image_base64)
        with self._infer_lock:
            self.get_image_embedding(abs_path=abs_path, b64_data=image_base64)
            self.get_language_features(prompt=prompt)
        return {"success": True}

    def start_background_workers(self):
        if self.enabled():
            def sam3_warmup():
                try:
                    time.sleep(2.0)
                except Exception:
                    pass
                try:
                    self.load_sessions()
                    self.get_tokenizer()
                    self.get_language_features(prompt="visual")
                    self.touch()
                except Exception:
                    pass
                try:
                    do_full = (os.environ.get("SAM3_WARMUP_FULL_SEGMENT", "0") or "0").strip() in (
                        "1",
                        "true",
                        "True",
                        "YES",
                        "yes",
                    )
                except Exception:
                    do_full = False
                if do_full:
                    try:
                        Image = self.get_pil_image()
                        image = Image.new("RGB", (1008, 1008), (0, 0, 0))
                        buffer = io.BytesIO()
                        image.save(buffer, format="JPEG", quality=80)
                        b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
                        self.run_segment(
                            b64_data=b64,
                            points=[{"x": 300, "y": 300, "label": 1}],
                            prompt="visual",
                        )
                    except Exception:
                        pass

            def sam3_idle_unload_loop():
                try:
                    try:
                        unload_sec = float(os.environ.get("SAM3_IDLE_UNLOAD_SEC", "300") or "300")
                    except Exception:
                        unload_sec = 300.0
                    if unload_sec <= 0:
                        return
                    max_check_sec = min(30.0, max(2.0, unload_sec / 10.0))
                    time.sleep(min(3.0, max_check_sec))
                    while True:
                        idle = self.get_idle_sec()
                        if idle is not None and idle >= unload_sec:
                            with self._infer_lock:
                                idle2 = self.get_idle_sec()
                                if idle2 is not None and idle2 >= unload_sec:
                                    self.unload()
                                    idle = None
                        if idle is None:
                            sleep_sec = max_check_sec
                        else:
                            remaining = max(0.0, unload_sec - idle)
                            sleep_sec = max(0.5, min(max_check_sec, remaining / 2.0))
                        time.sleep(sleep_sec)
                except Exception:
                    return

            threading.Thread(
                target=sam3_warmup,
                daemon=True,
                name="SAM3Warmup",
            ).start()
            threading.Thread(
                target=sam3_idle_unload_loop,
                daemon=True,
                name="SAM3IdleUnload",
            ).start()
        else:
            try:
                self.unload()
            except Exception:
                pass
