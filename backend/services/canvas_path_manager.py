import json
import os
import re
import shutil
import threading
import time


class CanvasPathManager:
    CAM_OUTPUT_VIRTUAL_PREFIX = "cam-output"

    def __init__(self, base_dir, legacy_canvas_dir=None, legacy_output_dir=None, legacy_uploads_dir=None):
        self._base_dir = os.path.abspath(base_dir)
        self._legacy_canvas_dir = legacy_canvas_dir
        self._legacy_output_dir = legacy_output_dir
        self._legacy_uploads_dir = legacy_uploads_dir
        self._active_canvas_name = ""
        self._active_canvas_lock = threading.Lock()
        self._migration_errors = []
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        try:
            os.makedirs(self._base_dir, exist_ok=True)
        except OSError as exc:
            self._migration_errors.append(
                {"type": "base_dir_create_failed", "path": self._base_dir, "error": str(exc)}
            )

    @property
    def base_dir(self):
        return self._base_dir

    @staticmethod
    def _safe_canvas_name(value):
        name = re.sub(r'[\\/:*?"<>|]', "_", str(value or "").strip())
        name = re.sub(r"_+", "_", name).strip("_")
        return name or "unnamed_canvas"

    def get_canvas_dir(self, canvas_name):
        safe = self._safe_canvas_name(canvas_name)
        return os.path.join(self._base_dir, safe)

    def get_canvas_output_dir(self, canvas_name):
        return os.path.join(self.get_canvas_dir(canvas_name), "output")

    def get_canvas_uploads_dir(self, canvas_name):
        return os.path.join(self.get_canvas_dir(canvas_name), "uploads")

    def get_canvas_project_file(self, canvas_name):
        safe = self._safe_canvas_name(canvas_name)
        return os.path.join(self.get_canvas_dir(canvas_name), f"{safe}.json")

    def ensure_canvas_dir(self, canvas_name):
        canvas_dir = self.get_canvas_dir(canvas_name)
        output_dir = self.get_canvas_output_dir(canvas_name)
        uploads_dir = self.get_canvas_uploads_dir(canvas_name)
        errors = []
        for d in (canvas_dir, output_dir, uploads_dir):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError as exc:
                errors.append({"type": "dir_create_failed", "path": d, "error": str(exc)})
        return errors

    def set_active_canvas(self, canvas_name):
        with self._active_canvas_lock:
            self._active_canvas_name = str(canvas_name or "").strip()

    def get_active_canvas(self):
        with self._active_canvas_lock:
            return self._active_canvas_name

    def canvas_dir_exists(self, canvas_name):
        return os.path.isdir(self.get_canvas_dir(canvas_name))

    def project_file_exists(self, canvas_name):
        return os.path.isfile(self.get_canvas_project_file(canvas_name))

    def list_canvas_projects(self):
        projects = []
        if not os.path.isdir(self._base_dir):
            return projects
        try:
            entries = os.listdir(self._base_dir)
        except OSError:
            return projects
        for entry in entries:
            entry_path = os.path.join(self._base_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            json_name = self._safe_canvas_name(entry) + ".json"
            json_path = os.path.join(entry_path, json_name)
            alt_json_path = os.path.join(entry_path, entry + ".json")
            found_json = None
            if os.path.isfile(json_path):
                found_json = json_path
            elif os.path.isfile(alt_json_path):
                found_json = alt_json_path
            else:
                for fn in os.listdir(entry_path):
                    if fn.endswith(".json") and not fn.startswith("."):
                        found_json = os.path.join(entry_path, fn)
                        break
            if found_json:
                try:
                    mtime = os.path.getmtime(found_json)
                except OSError:
                    mtime = 0
                projects.append(
                    {
                        "filename": os.path.basename(found_json),
                        "name": entry,
                        "mtime": mtime,
                        "canvasDir": entry_path,
                        "source": "cam-output",
                    }
                )
            else:
                projects.append(
                    {
                        "filename": "",
                        "name": entry,
                        "mtime": 0,
                        "canvasDir": entry_path,
                        "source": "cam-output",
                        "isExternalProject": True,
                    }
                )
        projects.sort(key=lambda item: item["mtime"], reverse=True)
        return projects

    def resolve_canvas_virtual_path(self, virtual_path):
        norm = str(virtual_path or "").replace("\\", "/").strip()
        prefix = self.CAM_OUTPUT_VIRTUAL_PREFIX + "/"
        if not norm.startswith(prefix):
            return None
        rest = norm[len(prefix):]
        parts = [p for p in rest.split("/") if p and p != "."]
        if len(parts) < 2:
            return None
        canvas_name = parts[0]
        sub_section = parts[1]
        rel_parts = parts[2:]
        canvas_dir = self.get_canvas_dir(canvas_name)
        if sub_section == "output":
            target_dir = self.get_canvas_output_dir(canvas_name)
        elif sub_section in ("uploads", "data"):
            target_dir = self.get_canvas_uploads_dir(canvas_name)
        else:
            target_dir = os.path.join(canvas_dir, sub_section)
        if rel_parts:
            abs_path = os.path.abspath(os.path.join(target_dir, *rel_parts))
        else:
            abs_path = os.path.abspath(target_dir)
        if not self._is_path_inside(abs_path, canvas_dir):
            return None
        return abs_path

    def build_canvas_virtual_path(self, canvas_name, section, rel_path=""):
        safe = self._safe_canvas_name(canvas_name)
        parts = [self.CAM_OUTPUT_VIRTUAL_PREFIX, safe, section]
        if rel_path:
            clean = str(rel_path).replace("\\", "/").strip("/")
            if clean:
                parts.append(clean)
        return "/".join(parts)

    def migrate_legacy_project(self, project_name, legacy_json_path):
        errors = []
        canvas_dir = self.get_canvas_dir(project_name)
        target_json = self.get_canvas_project_file(project_name)
        if os.path.isdir(canvas_dir) and not os.path.isfile(target_json):
            for fn in os.listdir(canvas_dir):
                if fn.endswith(".json") and not fn.startswith("."):
                    target_json = os.path.join(canvas_dir, fn)
                    break
        dir_errors = self.ensure_canvas_dir(project_name)
        errors.extend(dir_errors)
        if dir_errors:
            return {"success": False, "errors": errors}
        if not os.path.isfile(target_json):
            try:
                shutil.copy2(legacy_json_path, target_json)
            except (OSError, shutil.Error) as exc:
                errors.append(
                    {"type": "json_copy_failed", "src": legacy_json_path, "dst": target_json, "error": str(exc)}
                )
                return {"success": False, "errors": errors}
        try:
            with open(target_json, "r", encoding="utf-8-sig") as f:
                project_data = json.load(f)
        except Exception as exc:
            errors.append({"type": "json_read_failed", "path": target_json, "error": str(exc)})
            return {"success": False, "errors": errors}
        migrated_data = self._migrate_project_paths(project_data, project_name)
        try:
            tmp = target_json + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(migrated_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target_json)
        except OSError as exc:
            errors.append({"type": "json_write_failed", "path": target_json, "error": str(exc)})
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
        if self._legacy_output_dir and os.path.isdir(self._legacy_output_dir):
            self._migrate_media_dir(
                self._legacy_output_dir,
                self.get_canvas_output_dir(project_name),
                project_name,
                "output",
                errors,
            )
        if self._legacy_uploads_dir and os.path.isdir(self._legacy_uploads_dir):
            self._migrate_media_dir(
                self._legacy_uploads_dir,
                self.get_canvas_uploads_dir(project_name),
                project_name,
                "uploads",
                errors,
            )
        return {"success": len(errors) == 0, "errors": errors}

    def _migrate_project_paths(self, project_data, canvas_name):
        if not isinstance(project_data, dict):
            return project_data
        data_str = json.dumps(project_data, ensure_ascii=False)
        canvas_prefix = f"{self.CAM_OUTPUT_VIRTUAL_PREFIX}/{self._safe_canvas_name(canvas_name)}"
        data_str = data_str.replace('"output/', f'"{canvas_prefix}/output/')
        data_str = data_str.replace('"data/uploads/', f'"{canvas_prefix}/uploads/')
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            return project_data

    def _migrate_media_dir(self, src_dir, dst_dir, canvas_name, section, errors):
        if not os.path.isdir(src_dir):
            return
        try:
            os.makedirs(dst_dir, exist_ok=True)
        except OSError as exc:
            errors.append({"type": "dir_create_failed", "path": dst_dir, "error": str(exc)})
            return
        for root, dirs, files in os.walk(src_dir):
            rel_root = os.path.relpath(root, src_dir)
            target_root = dst_dir if rel_root == "." else os.path.join(dst_dir, rel_root)
            for dirname in dirs:
                target_subdir = os.path.join(target_root, dirname)
                try:
                    os.makedirs(target_subdir, exist_ok=True)
                except OSError as exc:
                    errors.append({"type": "dir_create_failed", "path": target_subdir, "error": str(exc)})
            for filename in files:
                if filename.startswith("."):
                    continue
                src_file = os.path.join(root, filename)
                dst_file = os.path.join(target_root, filename)
                if os.path.exists(dst_file):
                    continue
                try:
                    shutil.copy2(src_file, dst_file)
                except (OSError, shutil.Error) as exc:
                    errors.append(
                        {"type": "file_copy_failed", "src": src_file, "dst": dst_file, "error": str(exc)}
                    )

    def migrate_all_legacy_projects(self, legacy_canvas_dir):
        results = []
        if not os.path.isdir(legacy_canvas_dir):
            return results
        try:
            entries = os.listdir(legacy_canvas_dir)
        except OSError:
            return results
        for filename in entries:
            if not filename.endswith(".json"):
                continue
            json_path = os.path.join(legacy_canvas_dir, filename)
            if not os.path.isfile(json_path):
                continue
            project_name = filename[:-5]
            canvas_dir = self.get_canvas_dir(project_name)
            if os.path.isdir(canvas_dir):
                results.append(
                    {"name": project_name, "status": "skipped", "reason": "canvas_dir_already_exists"}
                )
                continue
            result = self.migrate_legacy_project(project_name, json_path)
            results.append(
                {
                    "name": project_name,
                    "status": "migrated" if result["success"] else "failed",
                    "errors": result.get("errors", []),
                }
            )
        return results

    def validate_storage_structure(self):
        issues = []
        suggestions = []
        if not os.path.isdir(self._base_dir):
            issues.append(
                {
                    "type": "base_dir_missing",
                    "path": self._base_dir,
                    "message": f"基础目录不存在: {self._base_dir}",
                }
            )
            suggestions.append(
                {"action": "create_base_dir", "path": self._base_dir, "message": "创建基础目录"}
            )
            return {"valid": False, "issues": issues, "suggestions": suggestions}
        try:
            test_file = os.path.join(self._base_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except OSError as exc:
            issues.append(
                {
                    "type": "permission_denied",
                    "path": self._base_dir,
                    "message": f"基础目录无写入权限: {self._base_dir} ({exc})",
                }
            )
            suggestions.append(
                {
                    "action": "fix_permissions",
                    "path": self._base_dir,
                    "message": "请检查目录权限，确保当前用户有写入权限",
                }
            )
        canvas_projects = self.list_canvas_projects()
        for project in canvas_projects:
            canvas_name = project["name"]
            canvas_dir = self.get_canvas_dir(canvas_name)
            output_dir = self.get_canvas_output_dir(canvas_name)
            uploads_dir = self.get_canvas_uploads_dir(canvas_name)
            if not os.path.isdir(output_dir):
                issues.append(
                    {
                        "type": "missing_output_dir",
                        "canvas": canvas_name,
                        "path": output_dir,
                        "message": f"画布 '{canvas_name}' 缺少 output 目录",
                    }
                )
                suggestions.append(
                    {
                        "action": "create_canvas_subdir",
                        "path": output_dir,
                        "message": f"为画布 '{canvas_name}' 创建 output 目录",
                    }
                )
            if not os.path.isdir(uploads_dir):
                issues.append(
                    {
                        "type": "missing_uploads_dir",
                        "canvas": canvas_name,
                        "path": uploads_dir,
                        "message": f"画布 '{canvas_name}' 缺少 uploads 目录",
                    }
                )
                suggestions.append(
                    {
                        "action": "create_canvas_subdir",
                        "path": uploads_dir,
                        "message": f"为画布 '{canvas_name}' 创建 uploads 目录",
                    }
                )
            project_file = self.get_canvas_project_file(canvas_name)
            if not os.path.isfile(project_file):
                alt_found = False
                if os.path.isdir(canvas_dir):
                    for fn in os.listdir(canvas_dir):
                        if fn.endswith(".json") and not fn.startswith("."):
                            alt_found = True
                            break
                if not alt_found and not project.get("isExternalProject"):
                    issues.append(
                        {
                            "type": "missing_project_file",
                            "canvas": canvas_name,
                            "path": project_file,
                            "message": f"画布 '{canvas_name}' 缺少项目文件",
                        }
                    )
                    suggestions.append(
                        {
                            "action": "check_project_file",
                            "canvas": canvas_name,
                            "message": f"请检查画布 '{canvas_name}' 的项目文件是否存在",
                        }
                    )
        return {
            "valid": len(issues) == 0,
            "baseDir": self._base_dir,
            "canvasCount": len(canvas_projects),
            "issues": issues,
            "suggestions": suggestions,
        }

    def repair_storage_structure(self):
        repairs = []
        try:
            os.makedirs(self._base_dir, exist_ok=True)
        except OSError as exc:
            repairs.append({"action": "create_base_dir", "success": False, "error": str(exc)})
        canvas_projects = self.list_canvas_projects()
        for project in canvas_projects:
            canvas_name = project["name"]
            errors = self.ensure_canvas_dir(canvas_name)
            if errors:
                repairs.extend(
                    [
                        {"action": "ensure_canvas_dir", "canvas": canvas_name, "success": False, "errors": errors}
                    ]
                )
            else:
                repairs.append({"action": "ensure_canvas_dir", "canvas": canvas_name, "success": True})
        return repairs

    def adopt_existing_directory(self, dir_path):
        dir_path = os.path.abspath(dir_path)
        if not os.path.isdir(dir_path):
            return {"success": False, "error": f"目录不存在: {dir_path}"}
        dir_name = os.path.basename(dir_path)
        canvas_dir = self.get_canvas_dir(dir_name)
        if os.path.normcase(os.path.abspath(dir_path)) == os.path.normcase(canvas_dir):
            self.ensure_canvas_dir(dir_name)
            return {"success": True, "action": "adopted", "canvasName": dir_name, "canvasDir": canvas_dir}
        if os.path.isdir(canvas_dir):
            return {"success": False, "error": f"画布目录已存在: {canvas_dir}"}
        try:
            shutil.move(dir_path, canvas_dir)
        except (OSError, shutil.Error) as exc:
            return {"success": False, "error": f"移动目录失败: {exc}"}
        self.ensure_canvas_dir(dir_name)
        return {"success": True, "action": "moved", "canvasName": dir_name, "canvasDir": canvas_dir}

    def scan_for_external_projects(self):
        external = []
        if not os.path.isdir(self._base_dir):
            return external
        for entry in os.listdir(self._base_dir):
            entry_path = os.path.join(self._base_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            has_json = False
            for fn in os.listdir(entry_path):
                if fn.endswith(".json") and not fn.startswith("."):
                    has_json = True
                    break
            if not has_json:
                has_media = False
                for sub in ("output", "outputs", "uploads", "data", "images", "videos"):
                    if os.path.isdir(os.path.join(entry_path, sub)):
                        has_media = True
                        break
                if has_media:
                    external.append(
                        {
                            "name": entry,
                            "path": entry_path,
                            "type": "external_project_no_json",
                            "message": f"检测到外部项目目录 '{entry}'，包含媒体文件但无项目JSON",
                        }
                    )
        return external

    @staticmethod
    def _is_path_inside(candidate, root):
        try:
            candidate_abs = os.path.normcase(os.path.abspath(candidate))
            root_abs = os.path.normcase(os.path.abspath(root))
            return os.path.commonpath([candidate_abs, root_abs]) == root_abs
        except Exception:
            return False

    def get_canvas_info(self, canvas_name):
        canvas_dir = self.get_canvas_dir(canvas_name)
        if not os.path.isdir(canvas_dir):
            return None
        output_dir = self.get_canvas_output_dir(canvas_name)
        uploads_dir = self.get_canvas_uploads_dir(canvas_name)
        project_file = self.get_canvas_project_file(canvas_name)
        output_count = 0
        uploads_count = 0
        if os.path.isdir(output_dir):
            for _, _, files in os.walk(output_dir):
                output_count += len(files)
        if os.path.isdir(uploads_dir):
            for _, _, files in os.walk(uploads_dir):
                uploads_count += len(files)
        return {
            "name": canvas_name,
            "canvasDir": canvas_dir,
            "projectFile": project_file,
            "outputDir": output_dir,
            "uploadsDir": uploads_dir,
            "hasProjectFile": os.path.isfile(project_file),
            "outputFileCount": output_count,
            "uploadsFileCount": uploads_count,
        }
