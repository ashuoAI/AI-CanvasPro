import hashlib
import json
import os
import random
import subprocess
import time


class LocalMediaProcessingRouteService:
    def __init__(
        self,
        *,
        output_dir_getter,
        resolve_local_virtual_path,
        read_body,
        path_exists=os.path.exists,
        ffmpeg_getter=lambda: "ffmpeg",
        ffprobe_getter=lambda: "ffprobe",
    ):
        self._get_output_dir = output_dir_getter
        self._resolve_local_virtual_path = resolve_local_virtual_path
        self._read_body = read_body
        self._path_exists = path_exists
        self._get_ffmpeg = ffmpeg_getter
        self._get_ffprobe = ffprobe_getter

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
            return None, LocalMediaProcessingRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, LocalMediaProcessingRouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _startupinfo():
        if os.name != "nt":
            return None
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo

    @staticmethod
    def _parse_ratio(value):
        try:
            raw = (value or "").strip()
            if not raw:
                return 0.0
            if "/" in raw:
                numerator, denominator = raw.split("/", 1)
                denominator_value = float(denominator)
                if denominator_value == 0:
                    return 0.0
                return float(numerator) / denominator_value
            return float(raw)
        except Exception:
            return 0.0

    @staticmethod
    def _normalize_fps_int(fps_value):
        if not fps_value or fps_value <= 0:
            return None
        buckets = (24, 25, 30, 50, 60)
        closest = None
        closest_delta = 999.0
        for bucket in buckets:
            delta = abs(float(fps_value) - float(bucket))
            if delta < closest_delta:
                closest_delta = delta
                closest = bucket
        fps_int = (
            int(closest)
            if closest is not None and closest_delta <= 0.2
            else int(round(fps_value))
        )
        return fps_int if fps_int > 0 else None

    def _output_dir(self):
        return os.path.abspath(self._get_output_dir())

    def _ffmpeg(self):
        return str(self._get_ffmpeg() or "ffmpeg")

    def _ffprobe(self):
        return str(self._get_ffprobe() or "ffprobe")

    def _read_json_request(self, handler):
        return self._parse_json_object(self._read_body(handler))

    def _validate_src_path(self, src_path, *, missing_message):
        src = (src_path or "").strip()
        if not src:
            return None, self._json_err(400, "Missing src")
        safe_src = src.lstrip("/")
        norm_src = os.path.normpath(safe_src)
        if (
            norm_src.startswith("..")
            or norm_src.startswith("../")
            or norm_src.startswith("..\\")
        ):
            return None, self._json_err(400, "Invalid src path")
        local_src = self._resolve_local_virtual_path(src)
        if not local_src or not self._path_exists(local_src):
            return None, self._json_err(404, missing_message)
        return local_src, None

    @staticmethod
    def _new_filename(prefix, ext):
        ts = int(time.time() * 1000)
        rand_str = f"{random.randint(100, 999)}"
        return f"{prefix}_{ts}_{rand_str}.{ext}"

    def _run_process(self, cmd, *, timeout, startupinfo=None):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            raise
        return process.returncode, stdout, stderr

    def _read_ffprobe_json(self, cmd, *, timeout, startupinfo):
        returncode, stdout, _ = self._run_process(
            cmd,
            timeout=timeout,
            startupinfo=startupinfo,
        )
        if returncode != 0:
            return None
        text = (stdout or b"").decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    def _ffprobe_video_fps_int(self, path, startupinfo):
        meta = self._read_ffprobe_json(
            [
                self._ffprobe(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                path,
            ],
            timeout=20,
            startupinfo=startupinfo,
        )
        streams = meta.get("streams") if isinstance(meta, dict) else []
        if not streams:
            return None
        stream = streams[0] if isinstance(streams[0], dict) else {}
        avg = (stream.get("avg_frame_rate") or "").strip()
        fallback = (stream.get("r_frame_rate") or "").strip()
        candidate = avg if avg and avg not in ("0/0", "0") else fallback
        fps_value = self._parse_ratio(candidate)
        return self._normalize_fps_int(fps_value)

    def _ffprobe_has_audio(self, path, startupinfo):
        cmd = [
            self._ffprobe(),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
        returncode, stdout, _ = self._run_process(cmd, timeout=15, startupinfo=startupinfo)
        if returncode != 0:
            return False
        text = (stdout or b"").decode("utf-8", errors="ignore").strip().lower()
        return "audio" in text

    def _ffprobe_video_wh(self, path, startupinfo):
        meta = self._read_ffprobe_json(
            [
                self._ffprobe(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                path,
            ],
            timeout=20,
            startupinfo=startupinfo,
        )
        streams = meta.get("streams") if isinstance(meta, dict) else []
        if not streams:
            return None
        stream = streams[0] if isinstance(streams[0], dict) else {}
        try:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        except Exception:
            return None
        if width <= 0 or height <= 0:
            return None
        return width, height

    def _handle_video_cut(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or "").strip()
        try:
            start_sec = float(data.get("start", 0))
            end_sec = float(data.get("end", 0))
        except Exception:
            return self._json_err(400, "Invalid parameters")
        if not src_path or end_sec <= start_sec:
            return self._json_err(400, "Invalid parameters")

        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        cut_dir = os.path.join(self._output_dir(), "CutVideo")
        os.makedirs(cut_dir, exist_ok=True)
        filename = self._new_filename("cut", "mp4")
        out_path = os.path.join(cut_dir, filename)

        try:
            cmd = [
                self._ffmpeg(),
                "-y",
                "-i",
                local_src,
                "-ss",
                str(start_sec),
                "-t",
                str(end_sec - start_sec),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                out_path,
            ]
            startupinfo = self._startupinfo()
            fps_int = self._ffprobe_video_fps_int(local_src, startupinfo)
            if fps_int:
                cmd.insert(-1, "-r")
                cmd.insert(-1, str(fps_int))

            returncode, _, stderr = self._run_process(
                cmd,
                timeout=120,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                print(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
                return self._json_err(500, "FFmpeg processing failed")
            return self._json_ok(
                {
                    "success": True,
                    "filename": filename,
                    "path": f"output/CutVideo/{filename}",
                    "localPath": f"output/CutVideo/{filename}",
                    "url": f"/output/CutVideo/{filename}",
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error processing video: {str(exc)}")

    def _handle_audio_cut(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or "").strip()
        try:
            start_sec = float(data.get("start", 0))
            end_sec = float(data.get("end", 0))
        except Exception:
            return self._json_err(400, "Invalid parameters")
        if not src_path or end_sec <= start_sec:
            return self._json_err(400, "Invalid parameters")

        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source audio not found",
        )
        if error is not None:
            return error

        cut_dir = os.path.join(self._output_dir(), "CutAudio")
        os.makedirs(cut_dir, exist_ok=True)
        filename = self._new_filename("cut", "mp3")
        out_path = os.path.join(cut_dir, filename)

        try:
            cmd = [
                self._ffmpeg(),
                "-y",
                "-i",
                local_src,
                "-ss",
                str(start_sec),
                "-t",
                str(end_sec - start_sec),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                out_path,
            ]
            returncode, _, stderr = self._run_process(
                cmd,
                timeout=120,
                startupinfo=self._startupinfo(),
            )
            if returncode != 0:
                print(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
                return self._json_err(500, "FFmpeg processing failed")
            return self._json_ok(
                {
                    "success": True,
                    "filename": filename,
                    "path": f"output/CutAudio/{filename}",
                    "localPath": f"output/CutAudio/{filename}",
                    "url": f"/output/CutAudio/{filename}",
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error processing audio: {str(exc)}")

    def _handle_video_separate_audio_video(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or "").strip()
        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        try:
            startupinfo = self._startupinfo()
            if not self._ffprobe_video_wh(local_src, startupinfo):
                return self._json_err(400, "Source video has no video stream")
            if not self._ffprobe_has_audio(local_src, startupinfo):
                return self._json_err(400, "当前视频没有可分离的音频")

            video_dir = os.path.join(self._output_dir(), "SeparateVideo")
            audio_dir = os.path.join(self._output_dir(), "SeparateAudio")
            os.makedirs(video_dir, exist_ok=True)
            os.makedirs(audio_dir, exist_ok=True)

            video_filename = self._new_filename("video", "mp4")
            audio_filename = self._new_filename("audio", "mp3")
            video_path = os.path.join(video_dir, video_filename)
            audio_path = os.path.join(audio_dir, audio_filename)

            video_cmd = [
                self._ffmpeg(),
                "-y",
                "-i",
                local_src,
                "-map",
                "0:v:0",
                "-an",
                "-c:v",
                "copy",
                video_path,
            ]
            returncode, _, stderr = self._run_process(
                video_cmd,
                timeout=300,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(
                    500,
                    f"FFmpeg video separation failed: {err_text or 'unknown error'}",
                )

            audio_cmd = [
                self._ffmpeg(),
                "-y",
                "-i",
                local_src,
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                audio_path,
            ]
            returncode, _, stderr = self._run_process(
                audio_cmd,
                timeout=300,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(
                    500,
                    f"FFmpeg audio separation failed: {err_text or 'unknown error'}",
                )

            video_rel_path = f"output/SeparateVideo/{video_filename}"
            audio_rel_path = f"output/SeparateAudio/{audio_filename}"
            return self._json_ok(
                {
                    "success": True,
                    "video": {
                        "filename": video_filename,
                        "path": video_rel_path,
                        "localPath": video_rel_path,
                        "url": f"/{video_rel_path}",
                    },
                    "audio": {
                        "filename": audio_filename,
                        "path": audio_rel_path,
                        "localPath": audio_rel_path,
                        "url": f"/{audio_rel_path}",
                    },
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error separating video audio: {str(exc)}")

    def _handle_video_compose(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        sources = data.get("srcs") or data.get("sources") or []
        if not isinstance(sources, list) or len(sources) < 2:
            return self._json_err(400, "Invalid srcs")
        if len(sources) > 80:
            return self._json_err(400, "Too many clips")

        abs_sources = []
        for source in sources:
            try:
                source_path = (source or "").strip()
            except Exception:
                source_path = ""
            if not source_path:
                return self._json_err(400, "Invalid srcs")
            local_src, error = self._validate_src_path(
                source_path,
                missing_message="Source video not found",
            )
            if error is not None:
                return error
            abs_sources.append(local_src)

        out_dir = os.path.join(self._output_dir(), "ComposeVideo")
        os.makedirs(out_dir, exist_ok=True)
        filename = self._new_filename("compose", "mp4")
        out_path = os.path.join(out_dir, filename)

        try:
            startupinfo = self._startupinfo()
            fps_int = self._ffprobe_video_fps_int(abs_sources[0], startupinfo) or 30
            wh = self._ffprobe_video_wh(abs_sources[0], startupinfo)
            if not wh:
                return self._json_err(500, "FFprobe failed: missing width/height")
            target_w, target_h = wh
            has_audio = True
            for path in abs_sources:
                if not self._ffprobe_has_audio(path, startupinfo):
                    has_audio = False
                    break

            cmd = [self._ffmpeg(), "-y"]
            for path in abs_sources:
                cmd.extend(["-i", path])

            parts = []
            for index in range(len(abs_sources)):
                parts.append(
                    f"[{index}:v]"
                    f"scale={int(target_w)}:{int(target_h)}:force_original_aspect_ratio=decrease,"
                    f"pad={int(target_w)}:{int(target_h)}:(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1,"
                    f"fps={int(fps_int)},"
                    f"format=yuv420p,"
                    f"setpts=PTS-STARTPTS[v{index}]"
                )
                if has_audio:
                    parts.append(
                        f"[{index}:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{index}]"
                    )
            if has_audio:
                join = "".join([f"[v{index}][a{index}]" for index in range(len(abs_sources))])
                parts.append(f"{join}concat=n={len(abs_sources)}:v=1:a=1[v][a]")
            else:
                join = "".join([f"[v{index}]" for index in range(len(abs_sources))])
                parts.append(f"{join}concat=n={len(abs_sources)}:v=1:a=0[v]")

            cmd.extend(["-filter_complex", ";".join(parts), "-map", "[v]"])
            if has_audio:
                cmd.extend(["-map", "[a]"])
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    out_path,
                ]
            )

            returncode, _, stderr = self._run_process(
                cmd,
                timeout=900,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(500, f"FFmpeg compose failed: {err_text or 'unknown error'}")
            rel_path = f"output/ComposeVideo/{filename}"
            return self._json_ok(
                {
                    "success": True,
                    "filename": filename,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": f"/{rel_path}",
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error composing video: {str(exc)}")

    def _handle_video_meta(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        local_src, error = self._validate_src_path(
            (data.get("src") or "").strip(),
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        try:
            cmd = [
                self._ffprobe(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=duration:stream=avg_frame_rate,r_frame_rate,nb_frames,duration,width,height",
                "-of",
                "json",
                local_src,
            ]
            startupinfo = self._startupinfo()
            returncode, stdout, stderr = self._run_process(
                cmd,
                timeout=20,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(500, f"FFprobe failed: {err_text or 'unknown error'}")

            try:
                meta = json.loads(stdout.decode("utf-8", errors="ignore") or "{}")
            except Exception:
                meta = {}

            streams = meta.get("streams") or []
            stream = streams[0] if streams else {}
            fmt = meta.get("format") or {}

            duration = 0.0
            try:
                duration = float(fmt.get("duration") or 0)
            except Exception:
                duration = 0.0
            if duration <= 0:
                try:
                    duration = float(stream.get("duration") or 0)
                except Exception:
                    duration = 0.0

            fps = self._parse_ratio(stream.get("avg_frame_rate") or "") or self._parse_ratio(
                stream.get("r_frame_rate") or "",
            )

            frame_count = 0
            try:
                if stream.get("nb_frames") is not None:
                    frame_count = int(float(stream.get("nb_frames")))
            except Exception:
                frame_count = 0
            if frame_count <= 0 and fps > 0 and duration > 0:
                frame_count = int(round(duration * fps))

            try:
                width = int(float(stream.get("width") or 0))
            except Exception:
                width = 0
            try:
                height = int(float(stream.get("height") or 0))
            except Exception:
                height = 0

            return self._json_ok(
                {
                    "success": True,
                    "fps": fps if fps > 0 else None,
                    "frameCount": frame_count if frame_count > 0 else None,
                    "duration": duration if duration > 0 else None,
                    "width": width if width > 0 else None,
                    "height": height if height > 0 else None,
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFprobe process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error reading video meta: {str(exc)}")

    def _handle_video_first_frame(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or "").strip()
        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        try:
            stat_result = os.stat(local_src)
        except Exception:
            return self._json_err(500, "Cannot stat source video")

        norm_src = os.path.normpath(src_path.lstrip("/"))
        signature = (
            f"{norm_src}|"
            f"{getattr(stat_result, 'st_mtime_ns', int(stat_result.st_mtime * 1e9))}|"
            f"{stat_result.st_size}"
        )
        digest = hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()[:12]

        thumb_dir = os.path.join(self._output_dir(), "VideoThumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        filename = f"vthumb_{digest}.jpg"
        out_path = os.path.join(thumb_dir, filename)

        if not os.path.exists(out_path):
            try:
                cmd = [
                    self._ffmpeg(),
                    "-y",
                    "-ss",
                    "0",
                    "-i",
                    local_src,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=240:-2",
                    "-q:v",
                    "8",
                    "-an",
                    out_path,
                ]
                returncode, _, stderr = self._run_process(
                    cmd,
                    timeout=30,
                    startupinfo=self._startupinfo(),
                )
                if returncode != 0:
                    print(
                        f"FFmpeg first_frame error: {(stderr or b'').decode('utf-8', errors='ignore')}"
                    )
                    return self._json_err(500, "FFmpeg processing failed")
            except subprocess.TimeoutExpired:
                return self._json_err(504, "FFmpeg process timeout")
            except Exception as exc:
                return self._json_err(500, f"Error extracting first frame: {str(exc)}")

        rel_path = f"output/VideoThumbs/{filename}"
        return self._json_ok({"success": True, "url": "/" + rel_path, "localPath": rel_path})

    def handle_post(self, handler, path):
        normalized = str(path or "").rstrip("/")
        if normalized == "/api/v2/video/cut":
            return self._handle_video_cut(handler)
        if normalized == "/api/v2/audio/cut":
            return self._handle_audio_cut(handler)
        if normalized == "/api/v2/video/separate_audio_video":
            return self._handle_video_separate_audio_video(handler)
        if normalized == "/api/v2/video/compose":
            return self._handle_video_compose(handler)
        if normalized == "/api/v2/video/meta":
            return self._handle_video_meta(handler)
        if normalized == "/api/v2/video/first_frame":
            return self._handle_video_first_frame(handler)
        return None
