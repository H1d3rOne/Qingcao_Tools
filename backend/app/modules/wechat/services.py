import atexit
import asyncio
import certifi
import json
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

import requests
import urllib3

from app.modules.wechat.constants import LOCAL_SERVER_PORT, PROXY_HOST, PROXY_PORT, to_size
from app.modules.wechat.local_server import LocalVideoServer
from app.modules.wechat.schemas import (
    ListenerStatus,
    WechatDownloadTaskItem,
    WechatDownloadTaskListResponse,
    WechatVideoItem,
    WechatVideoListResponse,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TaskCancelledError(RuntimeError):
    pass


class WechatService:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parents[4]
        self.module_dir = Path(__file__).resolve().parent
        self.data_dir = self.base_dir / "VideoDownload"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir = self.data_dir
        self.video_store_path = self.data_dir / "wechat_videos.jsonl"
        self.task_store_path = self.data_dir / "wechat_download_tasks.json"
        self.settings_store_path = self.data_dir / "wechat_settings.json"

        self._lock = threading.Lock()
        self._videos: Dict[str, dict] = {}
        self._tasks: Dict[str, dict] = {}
        self._last_error: Optional[str] = None
        self.proxy_controller = None
        self._task_thread: Optional[threading.Thread] = None
        self._task_processing = False
        self._cancel_requests: set[str] = set()

        self.local_server = LocalVideoServer("127.0.0.1", LOCAL_SERVER_PORT, self._ingest_video_payload)
        self._load_settings_from_store()
        self._load_tasks_from_store()
        atexit.register(self.shutdown)

    async def start_listener(self) -> ListenerStatus:
        return await asyncio.to_thread(self._start_listener_sync)

    async def stop_listener(self) -> ListenerStatus:
        return await asyncio.to_thread(self._stop_listener_sync)

    async def get_listener_status(self) -> ListenerStatus:
        return self.get_status()

    async def get_video_list(self) -> WechatVideoListResponse:
        items = [WechatVideoItem(**item) for item in self.list_videos()]
        return WechatVideoListResponse(items=items, total=len(items))

    async def clear_video_list(self) -> dict:
        return await asyncio.to_thread(self._clear_video_list_sync)

    async def get_download_task_list(self) -> WechatDownloadTaskListResponse:
        items = [WechatDownloadTaskItem(**item) for item in self.list_tasks()]
        return WechatDownloadTaskListResponse(items=items, total=len(items))

    async def queue_download(self, video_id: str) -> tuple[dict, str]:
        return await asyncio.to_thread(self._queue_download_sync, video_id)

    async def retry_download_task(self, task_id: str) -> dict:
        return await asyncio.to_thread(self._retry_download_task_sync, task_id)

    async def delete_download_task(self, task_id: str) -> dict:
        return await asyncio.to_thread(self._delete_download_task_sync, task_id)

    async def clear_download_tasks(self, statuses: Optional[List[str]] = None) -> dict:
        return await asyncio.to_thread(self._clear_download_tasks_sync, statuses)

    async def cancel_download_task(self, task_id: str) -> dict:
        return await asyncio.to_thread(self._cancel_download_task_sync, task_id)

    async def open_download_directory(self, task_id: str) -> dict:
        return await asyncio.to_thread(self._open_download_directory_sync, task_id)

    async def get_download_preview_path(self, task_id: str) -> str:
        return await asyncio.to_thread(self._get_download_preview_path_sync, task_id)

    async def set_download_dir(self, path: str) -> ListenerStatus:
        return await asyncio.to_thread(self._set_download_dir_sync, path)

    async def select_download_dir(self) -> tuple[ListenerStatus, bool]:
        return await asyncio.to_thread(self._select_download_dir_sync)

    async def download_video(self, video_id: str) -> dict:
        video = self.get_video(video_id)
        if not video:
            raise ValueError("视频不存在或已过期")
        return await asyncio.to_thread(self._download_and_decode, video_id, video)

    def get_status(self) -> ListenerStatus:
        controller = self.proxy_controller
        video_count = len(self.list_videos())
        return ListenerStatus(
            listening=bool(controller and controller.is_running and self.local_server.is_running),
            proxy_running=bool(controller and controller.is_running),
            local_server_running=self.local_server.is_running,
            system_proxy_enabled=bool(controller and controller.system_proxy_enabled),
            proxy_host=PROXY_HOST,
            proxy_port=PROXY_PORT,
            local_server_port=LOCAL_SERVER_PORT,
            video_count=video_count,
            download_dir=str(self.download_dir),
            last_error=self._last_error or (controller.last_error if controller else None),
        )

    def list_videos(self) -> List[dict]:
        self._load_videos_from_store()
        with self._lock:
            items = list(self._videos.values())
        items.sort(key=lambda item: item.get("created_at", 0), reverse=True)
        return items

    def get_video(self, video_id: str) -> Optional[dict]:
        with self._lock:
            video = self._videos.get(video_id)
        if video:
            return video

        self._load_videos_from_store()

        with self._lock:
            return self._videos.get(video_id)

    def list_tasks(self) -> List[dict]:
        self._load_tasks_from_store()
        with self._lock:
            items = list(self._tasks.values())
        items.sort(key=lambda item: item.get("created_at", 0), reverse=True)
        return items

    def clear_videos(self) -> None:
        with self._lock:
            self._videos.clear()
        if self.video_store_path.exists():
            self.video_store_path.unlink()

    def _clear_video_list_sync(self) -> dict:
        cleared_count = len(self.list_videos())
        self.clear_videos()
        return {"cleared_count": cleared_count}

    def _normalize_download_dir(self, path: Union[str, Path]) -> Path:
        value = Path(path).expanduser()
        if not value.is_absolute():
            value = value.resolve()
        return value

    def _set_download_dir_sync(self, path: str) -> ListenerStatus:
        value = (path or "").strip()
        if not value:
            raise ValueError("请填写下载目录")

        target_dir = self._normalize_download_dir(value)
        if target_dir.exists() and not target_dir.is_dir():
            raise ValueError("下载目录不是有效文件夹")

        target_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self.download_dir = target_dir
            self._persist_settings_locked()

        return self.get_status()

    def _select_download_dir_sync(self) -> tuple[ListenerStatus, bool]:
        selected_path = self._open_directory_picker_sync()
        if not selected_path:
            return self.get_status(), False
        return self._set_download_dir_sync(selected_path), True

    def _open_directory_picker_sync(self) -> Optional[str]:
        system = platform.system()

        if system == "Darwin":
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "请选择下载目录")'],
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()
            if result.returncode == 0:
                return output or None
            if "-128" in error or "User canceled" in error:
                return None
            raise RuntimeError(error or "打开目录选择器失败")

        if system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$dialog.Description = '请选择下载目录';"
                "$dialog.ShowNewFolderButton = $true;"
                "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
                "  [Console]::Out.Write($dialog.SelectedPath)"
                "}"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", script],
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()
            if result.returncode == 0:
                return output or None
            raise RuntimeError(error or "打开目录选择器失败")

        if shutil.which("zenity"):
            result = subprocess.run(
                ["zenity", "--file-selection", "--directory", "--title=请选择下载目录"],
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "").strip()
            if result.returncode == 0:
                return output or None
            if result.returncode == 1:
                return None
            raise RuntimeError((result.stderr or "").strip() or "打开目录选择器失败")

        if shutil.which("kdialog"):
            result = subprocess.run(
                ["kdialog", "--getexistingdirectory", str(self.download_dir)],
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "").strip()
            if result.returncode == 0:
                return output or None
            if result.returncode == 1:
                return None
            raise RuntimeError((result.stderr or "").strip() or "打开目录选择器失败")

        raise RuntimeError("当前系统不支持目录选择器")

    def shutdown(self) -> None:
        try:
            self._stop_listener_sync()
        except Exception:
            pass

    def _get_proxy_controller(self):
        if self.proxy_controller is None:
            from app.modules.wechat.proxy_server import ProxyController
            self.proxy_controller = ProxyController()
        return self.proxy_controller

    def _start_listener_sync(self) -> ListenerStatus:
        self.clear_videos()
        self._last_error = None
        self.local_server.start()
        try:
            self._get_proxy_controller().start()
        except Exception as exc:
            self.local_server.stop()
            self._last_error = str(exc)
            raise
        return self.get_status()

    def _stop_listener_sync(self) -> ListenerStatus:
        controller = self.proxy_controller
        if controller is not None:
            controller.stop()
        self.local_server.stop()
        self._ensure_task_processor()
        return self.get_status()

    def _ingest_video_payload(self, payload: dict) -> None:
        media_list = payload.get("media", [])
        if not media_list:
            raise ValueError("Missing media")

        media = media_list[0]
        description = (payload.get("description") or "").strip()
        url = f"{media.get('url', '')}{media.get('urlToken', '')}"
        decode_key = (media.get("decodeKey") or "").strip()
        file_size = int(media.get("fileSize", 0) or 0)

        video_id = self._build_video_id(url, decode_key, description, file_size)
        video = {
            "id": video_id,
            "description": description,
            "url": url,
            "cover_url": media.get("coverUrl", ""),
            "file_size": file_size,
            "file_size_text": to_size(file_size),
            "duration": int(media.get("videoPlayLen", 0) or 0),
            "decode_key": decode_key,
            "created_at": time.time(),
        }

        with self._lock:
            if video_id in self._videos:
                return
            self._videos[video_id] = video
            with self.video_store_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(video, ensure_ascii=False) + "\n")

    def _load_videos_from_store(self) -> None:
        if not self.video_store_path.exists():
            return

        loaded: Dict[str, dict] = {}
        with self.video_store_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                video_id = item.get("id")
                if video_id:
                    loaded[video_id] = item

        if not loaded:
            return

        with self._lock:
            self._videos.update(loaded)

    def _load_settings_from_store(self) -> None:
        if not self.settings_store_path.exists():
            self.download_dir = self.data_dir
            return

        try:
            with self.settings_store_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.download_dir = self.data_dir
            return

        path = (payload or {}).get("download_dir")
        if not path:
            self.download_dir = self.data_dir
            return

        target_dir = self._normalize_download_dir(path)
        target_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir = target_dir

    def _load_tasks_from_store(self) -> None:
        if not self.task_store_path.exists():
            return

        try:
            with self.task_store_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, list):
            return

        loaded: Dict[str, dict] = {}
        need_persist = False
        for item in payload:
            if not isinstance(item, dict):
                continue
            task_id = item.get("id")
            if task_id:
                normalized = self._normalize_task_item(item)
                if normalized.get("status") == "downloading":
                    normalized["status"] = "pending"
                    normalized["updated_at"] = time.time()
                    need_persist = True
                loaded[task_id] = normalized

        if not loaded:
            return

        with self._lock:
            self._tasks.update(loaded)
            if need_persist:
                self._persist_tasks_locked()

    def _persist_settings_locked(self) -> None:
        temp_path = self.settings_store_path.with_suffix(".tmp")
        payload = {"download_dir": str(self.download_dir)}
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.settings_store_path)

    def _persist_tasks_locked(self) -> None:
        items = sorted(self._tasks.values(), key=lambda item: item.get("created_at", 0), reverse=True)
        temp_path = self.task_store_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.task_store_path)

    def _build_task_id(self, video_id: str) -> str:
        import hashlib

        return hashlib.md5(f"task|{video_id}".encode("utf-8")).hexdigest()

    def _build_task_payload(self, task_id: str, video: dict, status: str = "pending") -> dict:
        now = time.time()
        return {
            "id": task_id,
            "video_id": video["id"],
            "description": video.get("description", ""),
            "cover_url": video.get("cover_url", ""),
            "file_size": int(video.get("file_size", 0) or 0),
            "file_size_text": video.get("file_size_text", to_size(int(video.get("file_size", 0) or 0))),
            "duration": int(video.get("duration", 0) or 0),
            "status": status,
            "progress": 0,
            "downloaded_size": 0,
            "downloaded_size_text": "0B",
            "raw_file": "",
            "decoded_file": "",
            "error": None,
            "created_at": now,
            "updated_at": now,
            "url": video.get("url", ""),
            "decode_key": video.get("decode_key", ""),
        }

    def _normalize_task_item(self, item: dict) -> dict:
        normalized = dict(item)
        file_size = int(normalized.get("file_size", 0) or 0)
        downloaded_size = int(normalized.get("downloaded_size", 0) or 0)
        status = normalized.get("status") or "pending"

        if status == "completed":
            progress = 100
            if file_size and downloaded_size <= 0:
                downloaded_size = file_size
        else:
            progress = int(normalized.get("progress", 0) or 0)
            progress = max(0, min(99 if status in {"pending", "downloading"} else 100, progress))

        normalized.update({
            "description": normalized.get("description", ""),
            "cover_url": normalized.get("cover_url", ""),
            "file_size": file_size,
            "file_size_text": normalized.get("file_size_text") or to_size(file_size),
            "duration": int(normalized.get("duration", 0) or 0),
            "status": status,
            "progress": progress,
            "downloaded_size": downloaded_size,
            "downloaded_size_text": normalized.get("downloaded_size_text") or to_size(downloaded_size),
            "raw_file": normalized.get("raw_file", ""),
            "decoded_file": normalized.get("decoded_file", ""),
            "error": normalized.get("error"),
            "created_at": float(normalized.get("created_at", 0) or 0),
            "updated_at": float(normalized.get("updated_at", normalized.get("created_at", 0)) or 0),
        })
        return normalized

    def _mark_task_cancel_requested(self, task_id: str) -> None:
        with self._lock:
            self._cancel_requests.add(task_id)

    def _clear_task_cancel_request(self, task_id: str) -> None:
        with self._lock:
            self._cancel_requests.discard(task_id)

    def _is_task_cancel_requested(self, task_id: Optional[str]) -> bool:
        if not task_id:
            return False
        with self._lock:
            return task_id in self._cancel_requests

    def _validate_task_statuses(self, statuses: Optional[List[str]]) -> List[str]:
        allowed = {"pending", "downloading", "completed", "failed"}
        values = statuses or ["completed", "failed"]
        normalized = []
        for item in values:
            value = (item or "").strip()
            if not value:
                continue
            if value not in allowed:
                raise ValueError(f"不支持的任务状态: {value}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    def _queue_download_sync(self, video_id: str) -> tuple[dict, str]:
        video = self.get_video(video_id)
        if not video:
            raise ValueError("视频不存在或已过期")

        task_id = self._build_task_id(video_id)
        task_snapshot = self._build_task_payload(task_id, video)
        action = "created"
        self._last_error = None
        self._clear_task_cancel_request(task_id)

        with self._lock:
            existing = self._tasks.get(task_id)
            if existing:
                existing.update({
                    "description": task_snapshot["description"],
                    "cover_url": task_snapshot["cover_url"],
                    "file_size": task_snapshot["file_size"],
                    "file_size_text": task_snapshot["file_size_text"],
                    "duration": task_snapshot["duration"],
                    "url": task_snapshot["url"],
                    "decode_key": task_snapshot["decode_key"],
                    "updated_at": time.time(),
                })
                if existing.get("status") not in {"pending", "downloading"}:
                    existing.update({
                        "status": "pending",
                        "progress": 0,
                        "downloaded_size": 0,
                        "downloaded_size_text": "0B",
                        "raw_file": "",
                        "decoded_file": "",
                        "error": None,
                    })
                    action = "requeued"
                else:
                    action = "existing"
                self._persist_tasks_locked()
                task = dict(existing)
            else:
                self._tasks[task_id] = task_snapshot
                self._persist_tasks_locked()
                task = dict(task_snapshot)

        self._ensure_task_processor()

        return task, action

    def _cancel_download_task_sync(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")

            status = task.get("status")
            if status == "downloading":
                self._cancel_requests.add(task_id)
                task["updated_at"] = time.time()
                self._persist_tasks_locked()
                return {"task_id": task_id, "status": "cancelling"}

            if status == "pending":
                task.update({
                    "status": "failed",
                    "progress": 0,
                    "downloaded_size": 0,
                    "downloaded_size_text": "0B",
                    "raw_file": "",
                    "decoded_file": "",
                    "error": "已取消下载",
                    "updated_at": time.time(),
                })
                self._persist_tasks_locked()
                return {"task_id": task_id, "status": "cancelled"}

            raise ValueError("当前任务无法取消")

    def _open_download_directory_sync(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")
            decoded_file = task.get("decoded_file", "")
            raw_file = task.get("raw_file", "")

        target_path = Path(decoded_file or raw_file or self.download_dir)
        if not target_path.exists():
            raise ValueError("文件或目录不存在")

        system = platform.system()
        if system == "Darwin":
            command = ["open", "-R", str(target_path)] if target_path.is_file() else ["open", str(target_path)]
        elif system == "Windows":
            command = ["explorer", f"/select,{str(target_path)}"] if target_path.is_file() else ["explorer", str(target_path)]
        else:
            command = ["xdg-open", str(target_path.parent if target_path.is_file() else target_path)]

        subprocess.run(command, check=True)
        return {"task_id": task_id, "path": str(target_path)}

    def _get_download_preview_path_sync(self, task_id: str) -> str:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")
            decoded_file = task.get("decoded_file", "")
            raw_file = task.get("raw_file", "")

        target_path = Path(decoded_file or raw_file)
        if not target_path.exists() or not target_path.is_file():
            raise ValueError("本地预览文件不存在")

        return str(target_path)

    def _retry_download_task_sync(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")
            if task.get("status") == "downloading":
                raise ValueError("下载中的任务暂不支持重试")
            self._cancel_requests.discard(task_id)

        video = self.get_video(task.get("video_id", "")) or task
        refresh_task = self._build_task_payload(task_id, video)

        with self._lock:
            current = self._tasks.get(task_id)
            if not current:
                raise ValueError("任务不存在")
            current.update({
                "description": refresh_task["description"],
                "cover_url": refresh_task["cover_url"],
                "file_size": refresh_task["file_size"],
                "file_size_text": refresh_task["file_size_text"],
                "duration": refresh_task["duration"],
                "status": "pending",
                "progress": 0,
                "downloaded_size": 0,
                "downloaded_size_text": "0B",
                "raw_file": "",
                "decoded_file": "",
                "error": None,
                "url": refresh_task["url"],
                "decode_key": refresh_task["decode_key"],
                "updated_at": time.time(),
            })
            self._persist_tasks_locked()
            task_snapshot = dict(current)

        self._ensure_task_processor()

        return task_snapshot

    def _delete_download_task_sync(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")
            if task.get("status") == "downloading":
                raise ValueError("下载中的任务暂不支持删除")

            self._cancel_requests.discard(task_id)
            self._tasks.pop(task_id, None)
            self._persist_tasks_locked()

        return {"task_id": task_id}

    def _clear_download_tasks_sync(self, statuses: Optional[List[str]] = None) -> dict:
        target_statuses = set(self._validate_task_statuses(statuses))
        if "downloading" in target_statuses:
            raise ValueError("下载中的任务不能被批量清空")

        with self._lock:
            removable_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.get("status") in target_statuses
            ]
            for task_id in removable_ids:
                self._cancel_requests.discard(task_id)
                self._tasks.pop(task_id, None)
            if removable_ids:
                self._persist_tasks_locked()

        return {"cleared_count": len(removable_ids), "statuses": list(target_statuses)}

    def _ensure_task_processor(self) -> None:
        if self._task_thread and self._task_thread.is_alive():
            return

        if not any(item.get("status") == "pending" for item in self.list_tasks()):
            return

        self._task_thread = threading.Thread(target=self._process_task_queue, name="wechat-download-tasks", daemon=True)
        self._task_thread.start()

    def _claim_next_pending_task(self) -> Optional[dict]:
        self._load_tasks_from_store()
        with self._lock:
            pending_tasks = [
                item for item in self._tasks.values()
                if item.get("status") == "pending"
            ]
            if not pending_tasks:
                return None

            pending_tasks.sort(key=lambda item: item.get("created_at", 0))
            task_id = pending_tasks[0]["id"]
            task = self._tasks[task_id]
            self._cancel_requests.discard(task_id)
            task.update({
                "status": "downloading",
                "progress": 0,
                "downloaded_size": 0,
                "downloaded_size_text": "0B",
                "error": None,
                "raw_file": "",
                "decoded_file": "",
                "updated_at": time.time(),
            })
            self._persist_tasks_locked()
            return dict(task)

    def _update_task(self, task_id: str, **changes) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.update(changes)
            task["updated_at"] = time.time()
            self._persist_tasks_locked()
            return dict(task)

    def _process_task_queue(self) -> None:
        self._task_processing = True
        try:
            while True:
                task = self._claim_next_pending_task()
                if not task:
                    break

                try:
                    video = self.get_video(task["video_id"]) or task
                    result = self._download_and_decode(task["video_id"], video, task_id=task["id"])
                    self._last_error = None
                    self._update_task(
                        task["id"],
                        status="completed",
                        progress=100,
                        downloaded_size=int(video.get("file_size", 0) or task.get("downloaded_size", 0) or 0),
                        downloaded_size_text=to_size(int(video.get("file_size", 0) or task.get("downloaded_size", 0) or 0)),
                        error=None,
                        raw_file=result["raw_file"],
                        decoded_file=result["decoded_file"],
                    )
                except TaskCancelledError as exc:
                    self._last_error = str(exc)
                    self._update_task(
                        task["id"],
                        status="failed",
                        error=str(exc),
                        raw_file="",
                        decoded_file="",
                    )
                except Exception as exc:
                    self._last_error = str(exc)
                    self._update_task(task["id"], status="failed", error=str(exc))
                finally:
                    self._clear_task_cancel_request(task["id"])
        finally:
            self._task_processing = False
            self._task_thread = None
            if any(item.get("status") == "pending" for item in self.list_tasks()):
                self._ensure_task_processor()

    def _download_and_decode(self, video_id: str, video: dict, task_id: Optional[str] = None) -> dict:
        description = self._safe_name(video.get("description") or f"wechat_video_{video_id[:8]}")
        download_dir = self.download_dir
        download_dir.mkdir(parents=True, exist_ok=True)
        raw_file = download_dir / f"{description}.__raw__.mp4"
        decoded_file = download_dir / f"{description}.mp4"

        last_progress = {"value": -1, "at": 0.0}

        def on_progress(downloaded_size: int, total_size: int) -> None:
            if not task_id:
                return

            if self._is_task_cancel_requested(task_id):
                raise TaskCancelledError("已取消下载")

            file_size = int(total_size or video.get("file_size", 0) or 0)
            if file_size > 0:
                progress = min(95, int(downloaded_size * 95 / file_size))
            else:
                progress = min(95, max(last_progress["value"], 5))

            now = time.time()
            if progress == last_progress["value"] and now - last_progress["at"] < 0.3 and downloaded_size < file_size:
                return

            last_progress["value"] = progress
            last_progress["at"] = now
            self._update_task(
                task_id,
                status="downloading",
                progress=progress,
                downloaded_size=downloaded_size,
                downloaded_size_text=to_size(downloaded_size),
                file_size=file_size or int(video.get("file_size", 0) or 0),
                file_size_text=to_size(file_size or int(video.get("file_size", 0) or 0)),
                error=None,
            )
        def cancel_check() -> bool:
            return self._is_task_cancel_requested(task_id)

        try:
            self._download_file(
                video["url"],
                raw_file,
                expected_total_size=int(video.get("file_size", 0) or 0),
                progress_callback=on_progress if task_id else None,
                cancel_check=cancel_check if task_id else None,
            )
            if task_id:
                final_size = int(video.get("file_size", 0) or raw_file.stat().st_size or 0)
                self._update_task(
                    task_id,
                    status="downloading",
                    progress=97,
                    downloaded_size=final_size,
                    downloaded_size_text=to_size(final_size),
                    file_size=final_size,
                    file_size_text=to_size(final_size),
                    error=None,
                )
            self._decode_file(raw_file, video["decode_key"], decoded_file, cancel_check=cancel_check if task_id else None)
            if raw_file.exists():
                raw_file.unlink()
            if task_id:
                final_size = int(video.get("file_size", 0) or decoded_file.stat().st_size or 0)
                self._update_task(
                    task_id,
                    status="downloading",
                    progress=100,
                    downloaded_size=final_size,
                    downloaded_size_text=to_size(final_size),
                    file_size=final_size,
                    file_size_text=to_size(final_size),
                    raw_file="",
                    decoded_file=str(decoded_file),
                    error=None,
                )
        except TaskCancelledError:
            if raw_file.exists():
                raw_file.unlink()
            if decoded_file.exists():
                decoded_file.unlink()
            raise

        return {
            "video_id": video_id,
            "description": video.get("description", ""),
            "raw_file": "",
            "decoded_file": str(decoded_file),
            "download_dir": str(download_dir),
        }

    def _build_video_id(self, url: str, decode_key: str, description: str, file_size: int) -> str:
        import hashlib

        raw = "|".join([url or "", decode_key or "", description or "", str(file_size)])
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _download_file(
        self,
        url: str,
        output_path: Path,
        expected_total_size: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        if output_path.exists():
            output_path.unlink()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090819) XWEB/11237 Flue",
            "Origin": "https://channels.weixin.qq.com",
            "Referer": "https://channels.weixin.qq.com/",
        }

        session = requests.Session()
        session.trust_env = False
        request_kwargs = {
            "headers": headers,
            "stream": True,
            "timeout": 120,
            "allow_redirects": True,
            "proxies": {"http": None, "https": None},
        }

        try:
            try:
                response = session.get(url, verify=certifi.where(), **request_kwargs)
            except requests.exceptions.SSLError:
                response = session.get(url, verify=False, **request_kwargs)

            response.raise_for_status()
            total_size = int(response.headers.get("Content-Length", 0) or 0) or int(expected_total_size or 0)
            downloaded_size = 0
            with output_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if cancel_check and cancel_check():
                        raise TaskCancelledError("已取消下载")
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded_size, total_size)
        finally:
            session.close()

    def _decode_file(
        self,
        input_path: Path,
        decode_key: str,
        output_path: Path,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        decrypt_script = self.module_dir / "scripts" / "decrypt.js"
        if not decrypt_script.exists():
            raise FileNotFoundError(f"decrypt.js 不存在: {decrypt_script}")
        if output_path.exists():
            output_path.unlink()

        process = subprocess.Popen(
            ["node", str(decrypt_script), str(input_path), str(decode_key), str(output_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(self.module_dir / "scripts"),
        )
        try:
            while True:
                if cancel_check and cancel_check():
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise TaskCancelledError("已取消下载")

                if process.poll() is not None:
                    break

                time.sleep(0.2)

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise RuntimeError((stderr or stdout or "解密失败").strip())
        finally:
            if process.poll() is None:
                process.kill()

    def _safe_name(self, name: str) -> str:
        safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name).strip(" ._")
        return safe[:120] or f"wechat_video_{int(time.time())}"
