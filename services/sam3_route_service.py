import json


class Sam3RouteService:
    def __init__(self, *, sam3_service):
        self.sam3_service = sam3_service

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
    def _binary(status, body, *, content_type, headers=None):
        payload = body if isinstance(body, (bytes, bytearray)) else bytes(body or b"")
        return {
            "kind": "binary",
            "status": int(status),
            "body": bytes(payload),
            "contentType": str(content_type or "application/octet-stream"),
            "headers": dict(headers or {}),
        }

    @staticmethod
    def _parse_json_object(body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            return None, Sam3RouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, Sam3RouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _segment_prompt(data):
        return data.get("textPrompt") or data.get("prompt") or "visual"

    def handle_get(self, handler, path):
        if path == "/api/v2/matting/sam3/info":
            return self._json_ok(self.sam3_service.build_info())
        return None

    def handle_post(self, handler, path, body):
        if path not in (
            "/api/v2/matting/sam3/segment",
            "/api/v2/matting/sam3/segment_raw",
            "/api/v2/matting/sam3/prepare",
        ):
            return None

        data, error = self._parse_json_object(body)
        if error is not None:
            return error
        if not self.sam3_service.enabled():
            return self._json_err(503, "SAM3 disabled")

        image_local_path = data.get("imageLocalPath") or data.get("localPath") or ""
        image_base64 = data.get("imageBase64") or ""

        try:
            if path == "/api/v2/matting/sam3/prepare":
                return self._json_ok(
                    self.sam3_service.prepare(
                        image_local_path=image_local_path,
                        image_base64=image_base64,
                        prompt=self._segment_prompt(data),
                    )
                )

            points = data.get("points") or []
            if not isinstance(points, list):
                return self._json_err(400, "Invalid points")

            if path == "/api/v2/matting/sam3/segment":
                return self._json_ok(
                    self.sam3_service.segment_png(
                        image_local_path=image_local_path,
                        image_base64=image_base64,
                        points=points,
                        prompt=self._segment_prompt(data),
                        single_point_box_px=data.get("singlePointBoxPx"),
                        multi_point_pad_ratio=data.get("multiPointPadRatio"),
                    )
                )

            raw = self.sam3_service.segment_raw(
                image_local_path=image_local_path,
                image_base64=image_base64,
                points=points,
                prompt=self._segment_prompt(data),
            )
            return self._binary(
                200,
                raw.get("body") or b"",
                content_type="application/octet-stream",
                headers={
                    "X-Mask-Width": str(int(raw.get("maskWidth") or 0)),
                    "X-Mask-Height": str(int(raw.get("maskHeight") or 0)),
                },
            )
        except ValueError as exc:
            return self._json_err(400, str(exc))
        except Exception as exc:
            return self._json_err(500, str(exc))
