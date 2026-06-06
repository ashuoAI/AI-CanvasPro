import hashlib
import json
import os
import random
import subprocess
import time


VIDEO_CLIP_FPS_OPTIONS = (16, 24, 30)
STORYBOARD_FRAME_MAX_COUNT = 100
STORYBOARD_FRAME_DEFAULT_COUNT = 100


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

    @staticmethod
    def _normalize_requested_clip_fps(value):
        if value is None or value == "":
            return None
        try:
            fps = int(round(float(value)))
        except Exception:
            return None
        return fps if fps in VIDEO_CLIP_FPS_OPTIONS else None

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

    @staticmethod
    def _normalize_storyboard_frame_count(value):
        try:
            count = int(round(float(value)))
        except Exception:
            count = STORYBOARD_FRAME_DEFAULT_COUNT
        return max(1, min(STORYBOARD_FRAME_MAX_COUNT, count))

    @staticmethod
    def _format_storyboard_frame_time(value):
        try:
            number = max(0.0, float(value))
        except Exception:
            number = 0.0
        return f"{number:.3f}".rstrip("0").rstrip(".") or "0"

    def _ffprobe_duration_sec(self, path, startupinfo):
        cmd = [
            self._ffprobe(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
        returncode, stdout, _ = self._run_process(
            cmd,
            timeout=20,
            startupinfo=startupinfo,
        )
        if returncode != 0:
            return 0.0
        text = (stdout or b"").decode("utf-8", errors="ignore").strip()
        try:
            duration = float(text) if text else 0.0
        except Exception:
            duration = 0.0
        return duration if duration > 0 else 0.0

    @staticmethod
    def _merge_storyboard_segments_to_limit(segments, limit):
        out = [list(seg) for seg in (segments or []) if len(seg) >= 2 and seg[1] > seg[0]]
        if limit <= 0:
            return []
        while len(out) > int(limit):
            shortest_i = min(
                range(len(out)),
                key=lambda index: float(out[index][1]) - float(out[index][0]),
            )
            if len(out) <= 1:
                break
            if shortest_i == 0:
                out[1] = [out[0][0], out[1][1]]
                out.pop(0)
            elif shortest_i == len(out) - 1:
                out[-2] = [out[-2][0], out[-1][1]]
                out.pop()
            else:
                left_d = out[shortest_i - 1][1] - out[shortest_i - 1][0]
                right_d = out[shortest_i + 1][1] - out[shortest_i + 1][0]
                if left_d <= right_d:
                    out[shortest_i - 1] = [out[shortest_i - 1][0], out[shortest_i][1]]
                    out.pop(shortest_i)
                else:
                    out[shortest_i + 1] = [out[shortest_i][0], out[shortest_i + 1][1]]
                    out.pop(shortest_i)
        return out

    @staticmethod
    def _build_equal_storyboard_segments(duration_sec, count):
        if count <= 0:
            return []
        if not duration_sec or duration_sec <= 0:
            return [[0.0, 0.0]]
        step = float(duration_sec) / float(count)
        segments = []
        for index in range(count):
            start = step * index
            end = float(duration_sec) if index == count - 1 else min(float(duration_sec), start + step)
            if end >= start:
                segments.append([float(start), float(end)])
        return segments

    def _detect_storyboard_scene_segments(self, local_src, duration_sec, count):
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
        except Exception:
            return []

        try:
            video = open_video(local_src)
            try:
                fps = float(getattr(video, "frame_rate", 0.0) or 0.0)
            except Exception:
                fps = 0.0
            if not fps or fps <= 0:
                fps = 30.0

            scene_manager = SceneManager()
            min_scene_len = max(1, int(round(0.6 * fps)))
            scene_manager.add_detector(
                ContentDetector(threshold=23.0, min_scene_len=min_scene_len)
            )
            scene_manager.detect_scenes(video, show_progress=False)
            scene_list = scene_manager.get_scene_list() or []
            segments = []
            for start_tc, end_tc in scene_list:
                try:
                    start = float(start_tc.get_seconds())
                    end = float(end_tc.get_seconds())
                except Exception:
                    continue
                if end > start:
                    segments.append([start, end])
            if len(segments) <= 1:
                return []
            return self._merge_storyboard_segments_to_limit(segments, count)
        except Exception:
            return []

    def _resolve_storyboard_frame_segments(self, local_src, duration_sec, count, exact_count):
        if exact_count:
            return self._build_equal_storyboard_segments(duration_sec, count)
        detected = self._detect_storyboard_scene_segments(local_src, duration_sec, count)
        if detected:
            return detected
        if duration_sec and duration_sec > 0:
            auto_count = max(1, int(round(float(duration_sec) / 2.0)))
            auto_count = min(count, auto_count)
        else:
            auto_count = 1
        return self._build_equal_storyboard_segments(duration_sec, auto_count)

    def _handle_video_storyboard_frames(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or "").strip()
        options = data.get("options") if isinstance(data.get("options"), dict) else {}
        count = self._normalize_storyboard_frame_count(
            options.get("maxFrames", options.get("frameCount", data.get("maxFrames")))
        )
        exact_count = bool(options.get("exactCount") or data.get("exactCount"))

        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        startupinfo = self._startupinfo()
        try:
            duration_sec = self._ffprobe_duration_sec(local_src, startupinfo)
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFprobe process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error reading video duration: {str(exc)}")

        try:
            stat_result = os.stat(local_src)
        except Exception:
            return self._json_err(500, "Cannot stat source video")

        norm_src = os.path.normpath(src_path.lstrip("/"))
        signature = (
            f"{norm_src}|"
            f"{getattr(stat_result, 'st_mtime_ns', int(stat_result.st_mtime * 1e9))}|"
            f"{stat_result.st_size}|{count}|{1 if exact_count else 0}"
        )
        digest = hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()[:12]
        frame_dir = os.path.join(self._output_dir(), "StoryboardFrames", digest)
        os.makedirs(frame_dir, exist_ok=True)

        segments = self._resolve_storyboard_frame_segments(
            local_src,
            duration_sec,
            count,
            exact_count,
        )
        if not segments:
            return self._json_err(500, "No storyboard frames could be resolved")

        frames = []
        for index, (start, end) in enumerate(segments[:count]):
            start = max(0.0, float(start))
            end = max(start, float(end))
            duration = max(0.0, end - start)
            offset = min(0.2, duration * 0.1) if duration > 0 else 0.0
            capture_time = start + offset
            if duration > 0:
                capture_time = min(max(start, capture_time), max(start, end - 0.001))

            start_tag = int(round(start * 1000))
            end_tag = int(round(end * 1000))
            filename = f"frame_{index + 1:03d}_{start_tag}-{end_tag}.jpg"
            out_path = os.path.join(frame_dir, filename)

            if not os.path.exists(out_path):
                cmd = [
                    self._ffmpeg(),
                    "-y",
                    "-ss",
                    self._format_storyboard_frame_time(capture_time),
                    "-i",
                    local_src,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    "-q:v",
                    "5",
                    "-an",
                    out_path,
                ]
                try:
                    returncode, _, stderr = self._run_process(
                        cmd,
                        timeout=45,
                        startupinfo=startupinfo,
                    )
                except subprocess.TimeoutExpired:
                    return self._json_err(504, "FFmpeg process timeout")
                if returncode != 0:
                    print(
                        f"FFmpeg storyboard frame error: {(stderr or b'').decode('utf-8', errors='ignore')}"
                    )
                    return self._json_err(500, "FFmpeg processing failed")

            rel_path = f"output/StoryboardFrames/{digest}/{filename}"
            frames.append(
                {
                    "index": index + 1,
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "captureTime": capture_time,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": "/" + rel_path,
                }
            )

        return self._json_ok(
            {
                "success": True,
                "src": src_path,
                "duration": duration_sec,
                "count": len(frames),
                "frames": frames,
            }
        )

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
        requested_fps = self._normalize_requested_clip_fps(
            data.get("fps", data.get("frameRate"))
        )

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
                "-ss",
                str(start_sec),
                "-t",
                str(end_sec - start_sec),
                "-i",
                local_src,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                out_path,
            ]
            startupinfo = self._startupinfo()
            fps_int = requested_fps
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
            payload = {
                "success": True,
                "filename": filename,
                "path": f"output/CutVideo/{filename}",
                "localPath": f"output/CutVideo/{filename}",
                "url": f"/output/CutVideo/{filename}",
            }
            if fps_int:
                payload["fps"] = fps_int
            return self._json_ok(payload)
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

    def _handle_video_clip_export(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        src_path = (data.get("src") or data.get("videoSrc") or "").strip()
        audio_src_path = (data.get("audioSrc") or "").strip()
        try:
            start_sec = float(data.get("start", data.get("videoStart", 0)))
            end_sec = float(data.get("end", data.get("videoEnd", 0)))
            audio_start_sec = float(data.get("audioStart", 0))
            audio_end_sec = float(data.get("audioEnd", 0))
        except Exception:
            return self._json_err(400, "Invalid parameters")
        if not src_path or end_sec <= start_sec:
            return self._json_err(400, "Invalid parameters")
        if audio_src_path and audio_end_sec <= audio_start_sec:
            return self._json_err(400, "Invalid audio parameters")

        local_src, error = self._validate_src_path(
            src_path,
            missing_message="Source video not found",
        )
        if error is not None:
            return error

        local_audio_src = ""
        if audio_src_path:
            local_audio_src, error = self._validate_src_path(
                audio_src_path,
                missing_message="Source audio not found",
            )
            if error is not None:
                return error

        out_dir = os.path.join(self._output_dir(), "ClipVideo")
        os.makedirs(out_dir, exist_ok=True)
        filename = self._new_filename("clip", "mp4")
        out_path = os.path.join(out_dir, filename)

        try:
            startupinfo = self._startupinfo()
            wh = self._ffprobe_video_wh(local_src, startupinfo)
            if not wh:
                return self._json_err(500, "FFprobe failed: missing width/height")
            video_duration = end_sec - start_sec
            cmd = [
                self._ffmpeg(),
                "-y",
                "-ss",
                str(start_sec),
                "-t",
                str(video_duration),
                "-i",
                local_src,
            ]
            if local_audio_src:
                audio_duration = audio_end_sec - audio_start_sec
                cmd.extend(
                    [
                        "-ss",
                        str(audio_start_sec),
                        "-t",
                        str(audio_duration),
                        "-i",
                        local_audio_src,
                        "-filter_complex",
                        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad[a]",
                        "-map",
                        "0:v:0",
                        "-map",
                        "[a]",
                        "-t",
                        str(video_duration),
                    ]
                )
            else:
                cmd.extend(["-map", "0:v:0", "-map", "0:a?"])
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    "high",
                    "-preset",
                    "fast",
                    "-c:a",
                    "aac",
                ]
            )
            fps_int = self._normalize_requested_clip_fps(
                data.get("fps", data.get("frameRate"))
            ) or self._ffprobe_video_fps_int(local_src, startupinfo)
            if fps_int:
                cmd.extend(["-r", str(fps_int)])
            cmd.extend(["-movflags", "+faststart", out_path])

            returncode, _, stderr = self._run_process(
                cmd,
                timeout=300,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(500, f"FFmpeg clip export failed: {err_text or 'unknown error'}")
            rel_path = f"output/ClipVideo/{filename}"
            return self._json_ok(
                {
                    "success": True,
                    "filename": filename,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": f"/{rel_path}",
                    "videoDuration": video_duration,
                    "fps": fps_int,
                    "videoWidth": wh[0],
                    "videoHeight": wh[1],
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error exporting clip: {str(exc)}")

    def _handle_audio_compose(self, handler):
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
                missing_message="Source audio not found",
            )
            if error is not None:
                return error
            abs_sources.append(local_src)

        out_dir = os.path.join(self._output_dir(), "ComposeAudio")
        os.makedirs(out_dir, exist_ok=True)
        filename = self._new_filename("compose", "mp3")
        out_path = os.path.join(out_dir, filename)

        try:
            startupinfo = self._startupinfo()
            for path in abs_sources:
                if not self._ffprobe_has_audio(path, startupinfo):
                    return self._json_err(400, "Source audio has no audio stream")

            cmd = [self._ffmpeg(), "-y"]
            for path in abs_sources:
                cmd.extend(["-i", path])

            parts = []
            for index in range(len(abs_sources)):
                parts.append(
                    f"[{index}:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{index}]"
                )
            join = "".join([f"[a{index}]" for index in range(len(abs_sources))])
            parts.append(f"{join}concat=n={len(abs_sources)}:v=0:a=1[a]")

            cmd.extend(
                [
                    "-filter_complex",
                    ";".join(parts),
                    "-map",
                    "[a]",
                    "-vn",
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
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
                return self._json_err(500, f"FFmpeg audio compose failed: {err_text or 'unknown error'}")
            rel_path = f"output/ComposeAudio/{filename}"
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
            return self._json_err(500, f"Error composing audio: {str(exc)}")

    def _handle_video_reverse(self, handler):
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
            wh = self._ffprobe_video_wh(local_src, startupinfo)
            if not wh:
                return self._json_err(400, "Source video has no video stream")
            duration = self._ffprobe_duration_sec(local_src, startupinfo)
            fps_int = self._ffprobe_video_fps_int(local_src, startupinfo)
            has_audio = self._ffprobe_has_audio(local_src, startupinfo)

            out_dir = os.path.join(self._output_dir(), "ReverseVideo")
            os.makedirs(out_dir, exist_ok=True)
            filename = self._new_filename("reverse", "mp4")
            out_path = os.path.join(out_dir, filename)

            filters = ["[0:v]reverse,setpts=PTS-STARTPTS,format=yuv420p[v]"]
            if has_audio:
                filters.append("[0:a]areverse,asetpts=PTS-STARTPTS[a]")

            cmd = [
                self._ffmpeg(),
                "-y",
                "-i",
                local_src,
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[v]",
            ]
            if has_audio:
                cmd.extend(["-map", "[a]"])
            else:
                cmd.append("-an")
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    "high",
                    "-preset",
                    "fast",
                ]
            )
            if has_audio:
                cmd.extend(["-c:a", "aac"])
            cmd.extend(["-movflags", "+faststart", out_path])

            returncode, _, stderr = self._run_process(
                cmd,
                timeout=600,
                startupinfo=startupinfo,
            )
            if returncode != 0:
                err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                return self._json_err(500, f"FFmpeg video reverse failed: {err_text or 'unknown error'}")

            rel_path = f"output/ReverseVideo/{filename}"
            return self._json_ok(
                {
                    "success": True,
                    "filename": filename,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": f"/{rel_path}",
                    "videoDuration": duration,
                    "fps": fps_int,
                    "videoWidth": wh[0],
                    "videoHeight": wh[1],
                }
            )
        except subprocess.TimeoutExpired:
            return self._json_err(504, "FFmpeg process timeout")
        except Exception as exc:
            return self._json_err(500, f"Error reversing video: {str(exc)}")

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
        if normalized == "/api/v2/video/clip_export":
            return self._handle_video_clip_export(handler)
        if normalized == "/api/v2/audio/compose":
            return self._handle_audio_compose(handler)
        if normalized == "/api/v2/video/reverse":
            return self._handle_video_reverse(handler)
        if normalized == "/api/v2/video/separate_audio_video":
            return self._handle_video_separate_audio_video(handler)
        if normalized == "/api/v2/video/compose":
            return self._handle_video_compose(handler)
        if normalized == "/api/v2/video/meta":
            return self._handle_video_meta(handler)
        if normalized == "/api/v2/video/first_frame":
            return self._handle_video_first_frame(handler)
        if normalized == "/api/v2/video/storyboard_frames":
            return self._handle_video_storyboard_frames(handler)
        return None
