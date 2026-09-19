from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROMPT_VERSION = "video_type_json_v1"
VIDEO_TYPES = {"知识干货类", "带货种草类", "闲聊Vlog类", "资讯热点类", "影视解说类"}


class PipelineError(Exception):
    def __init__(self, code: str, message: str, status: str = "failed"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def link_key(link: str) -> str:
    return hashlib.sha256(extract_share_url(link).encode("utf-8")).hexdigest()


def extract_share_url(text: str) -> str:
    raw = (text or "").strip()
    match = re.search(r"https?://[^\s，。'\"<>）)]+", raw)
    if not match:
        return raw
    url = match.group(0).strip()
    return url.rstrip(".,，。；;、")


def extract_share_title(text: str) -> str:
    raw = (text or "").strip()
    raw = re.sub(r"https?://\S+", "", raw)
    raw = re.sub(r"【小红书】.*$", "", raw).strip()
    raw = re.sub(r"【抖音】.*$", "", raw).strip()
    raw = re.sub(r"\s+", " ", raw).strip(" -_｜|。…")
    return raw[:80]


def infer_platform(link: str) -> str:
    low = (link or "").lower()
    if "xiaohongshu" in low or "xhs" in low:
        return "小红书"
    if "douyin" in low or "iesdouyin" in low:
        return "抖音"
    return "未知平台"


def http_json(url: str, data: dict, token: str = "", timeout: int = 20) -> dict:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def safe_error_text(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            if body:
                message = f"HTTP {exc.code}: {body[:300]}"
            else:
                message = f"HTTP {exc.code}: {exc.reason}"
        except Exception:
            message = f"HTTP {exc.code}: {exc.reason}"
    message = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", message)
    return message


def http_get_json(url: str, params: dict, token: str = "", timeout: int = 20) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in [None, ""]})
    headers = {"User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{url}?{query}", headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_tikhub_http_error(exc: urllib.error.HTTPError, endpoint: str) -> str:
    if exc.code in [401, 403, 444]:
        return f"HTTP {exc.code}：TikHub 拒绝访问 {endpoint}，请检查 API Key 权限、余额或接口套餐"
    return f"HTTP {exc.code}: {exc.reason}"


def resolve_redirect(link: str) -> str:
    req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.geturl()
    except Exception:
        return link


def fetch_public_meta(link: str) -> dict:
    clean_link = extract_share_url(link)
    title_hint = extract_share_title(link)
    if not clean_link.startswith(("http://", "https://")):
        raise PipelineError("INVALID_SHARE_LINK", "未识别到有效链接，请粘贴包含 http 开头链接的分享内容", "failed")
    final_url = resolve_redirect(clean_link)
    req = urllib.request.Request(final_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            page = resp.read(1024 * 1024).decode("utf-8", errors="ignore")
    except Exception as exc:
        raise PipelineError("LINK_FETCH_FAILED", f"链接页面读取失败：{exc}", "need_upload")

    def meta(prop: str) -> str:
        patterns = [
            rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
            rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pat in patterns:
            m = re.search(pat, page, re.I)
            if m:
                return html.unescape(m.group(1)).strip()
        return ""

    title = meta("og:title") or meta("twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    desc = meta("description") or meta("og:description")
    image = meta("og:image") or meta("twitter:image")

    return {
        "platform": infer_platform(final_url or link),
        "source_url": final_url or clean_link,
        "title": title or "未命名视频笔记",
        "author": "",
        "cover_url": image,
        "caption_text": desc,
        "subtitle_text": "",
        "images": [image] if image else [],
        "video_url": "",
        "raw": {"resolver": "public_meta"},
    }


def normalize_parser_result(link: str, data: dict) -> dict:
    root = data.get("data") if isinstance(data.get("data"), dict) else data
    return {
        "platform": root.get("platform") or infer_platform(link),
        "source_url": root.get("source_url") or root.get("url") or link,
        "title": root.get("title") or root.get("desc") or "未命名视频笔记",
        "author": root.get("author") or root.get("nickname") or root.get("source_account") or "",
        "cover_url": root.get("cover_url") or root.get("cover") or root.get("image") or "",
        "caption_text": root.get("caption") or root.get("desc") or root.get("text") or "",
        "subtitle_text": root.get("subtitle") or root.get("subtitles") or root.get("transcript") or root.get("asr_text") or root.get("speech_text") or "",
        "images": root.get("images") or root.get("image_list") or [],
        "video_url": root.get("video_url") or root.get("video") or root.get("play_url") or "",
        "raw": root,
    }


def deep_get(data, *keys):
    cur = data
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int) and len(cur) > key:
            cur = cur[key]
        else:
            return None
    return cur


def first_url(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            url = first_url(item)
            if url:
                return url
    if isinstance(value, dict):
        for key in ["url", "url_default", "url_pre", "url_list", "uri"]:
            url = first_url(value.get(key))
            if url:
                return url
    return ""


def collect_text(value, keys=("subtitle", "subtitles", "transcript", "caption", "text", "content", "desc")):
    texts = []
    def walk(node, key_name=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key_name)
        elif isinstance(node, str) and key_name in keys and len(node.strip()) > 6:
            texts.append(node.strip())
    walk(value)
    return "\n".join(dict.fromkeys(texts))


def find_media_url(value):
    candidates = []
    def walk(node, key_name=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key_name)
        elif isinstance(node, str) and node.startswith(("http://", "https://")):
            low = node.lower()
            score = 0
            if any(x in low for x in [".mp4", "video", "play", "stream"]): score += 3
            if any(x in key_name.lower() for x in ["video", "play", "stream", "media"]): score += 3
            if score:
                candidates.append((score, node))
    walk(value)
    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1] if candidates else ""


def is_video_source(source: dict, original_link: str = "") -> bool:
    raw = source.get("raw") or {}
    text = json.dumps(raw, ensure_ascii=False).lower() + " " + (original_link or "").lower() + " " + (source.get("source_url") or "").lower()
    if "type=video" in text or '"type": "video"' in text or '"note_type": "video"' in text:
        return True
    if source.get("video_url"):
        return True
    if source.get("local_video_path"):
        return True
    return False


def resolve_with_crv(link: str) -> dict:
    try:
        from claude_real_video import process as crv_process
    except ImportError:
        raise PipelineError("CRV_NOT_AVAILABLE", "未安装 claude-real-video，无法启用本地视频解析兜底。")

    clean_link = extract_share_url(link)
    title_hint = extract_share_title(link)
    out_dir = Path(tempfile.gettempdir()) / f"vkb-crv-{hashlib.md5(clean_link.encode()).hexdigest()}"
    try:
        result = crv_process(
            clean_link,
            str(out_dir),
            overwrite=True,
            do_transcribe=True,
            lang=os.getenv("WHISPER_LANG", "zh"),
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            max_frames=int(os.getenv("MAX_KEYFRAMES", "8")),
            fps_floor=float(os.getenv("CRV_FPS_FLOOR", "5")),
        )
    except Exception as exc:
        raise PipelineError("CRV_PARSE_FAILED", f"链接真实视频解析失败：{exc}", "failed")

    transcript = ""
    if result.transcript_path and Path(result.transcript_path).exists():
        transcript = Path(result.transcript_path).read_text(encoding="utf-8", errors="ignore")
    frames = []
    if result.frames_json_path and Path(result.frames_json_path).exists():
        try:
            meta = json.loads(Path(result.frames_json_path).read_text(encoding="utf-8", errors="ignore"))
            frames = [str(Path(result.frames_dir) / item["file"]) for item in meta.get("frames", []) if item.get("file")]
        except Exception:
            frames = []
    if content_signal(transcript) < int(os.getenv("MIN_TRANSCRIPT_CHARS", "120")):
        raise PipelineError("CRV_TRANSCRIPT_TOO_SHORT", "链接视频解析已完成，但音频转写内容过短，不生成假笔记。", "failed")
    return {
        "platform": infer_platform(link),
        "source_url": clean_link,
        "title": title_hint or clean_link,
        "author": "",
        "cover_url": frames[0] if frames else "",
        "caption_text": title_hint,
        "subtitle_text": transcript,
        "images": frames,
        "video_url": "",
        "local_video_path": result.video,
        "keyframes": frames,
        "raw": {"resolver": "claude_real_video", "duration": result.duration},
    }


def extract_keyframes_with_crv(link: str) -> list[str]:
    if os.getenv("CRV_ENABLED", "1") != "1":
        return []
    try:
        from claude_real_video import process as crv_process
    except ImportError:
        return []
    clean_link = extract_share_url(link)
    out_dir = Path(tempfile.gettempdir()) / f"vkb-crv-frames-{hashlib.md5(clean_link.encode()).hexdigest()}"
    try:
        result = crv_process(
            clean_link,
            str(out_dir),
            overwrite=True,
            do_transcribe=False,
            text_anchors=True,
            max_frames=int(os.getenv("OCR_MAX_KEYFRAMES", os.getenv("MAX_KEYFRAMES", "12"))),
            fps_floor=float(os.getenv("CRV_FPS_FLOOR", "5")),
        )
    except Exception:
        return []
    frames = []
    if result.frames_json_path and Path(result.frames_json_path).exists():
        try:
            meta = json.loads(Path(result.frames_json_path).read_text(encoding="utf-8", errors="ignore"))
            frames = [str(Path(result.frames_dir) / item["file"]) for item in meta.get("frames", []) if item.get("file")]
        except Exception:
            frames = []
    return frames[: int(os.getenv("OCR_MAX_KEYFRAMES", os.getenv("MAX_KEYFRAMES", "12")))]


def deyo_source_from_link(link: str) -> str:
    low = (link or "").lower()
    if "xiaohongshu" in low or "xhslink" in low or "xhs" in low:
        return "xiaohongshu"
    if "douyin" in low or "iesdouyin" in low:
        return "douyin"
    return ""


def find_deyo_cli() -> str:
    configured = os.getenv("DEYO_CLI", "").strip()
    if configured:
        return configured
    return shutil.which("deyo") or shutil.which("deyo.cmd") or ""


def resolve_with_deyo(link: str) -> dict:
    deyo_cli = find_deyo_cli()
    if not deyo_cli:
        raise PipelineError("DEYO_CLI_NOT_AVAILABLE", "未安装 Deyo CLI，无法通过 Deyo 解析链接。", "failed")
    clean_link = extract_share_url(link)
    title_hint = extract_share_title(link)
    out_dir = Path(tempfile.mkdtemp(prefix="vkb-deyo-"))
    raw_path = out_dir / "raw.txt"
    cmd = [deyo_cli, "--format", "text", "--progress-format", "jsonl", "-O", str(raw_path)]
    source = deyo_source_from_link(link)
    if source:
        cmd += ["--source", source]
    cmd.append(clean_link)
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(out_dir),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=int(os.getenv("DEYO_TIMEOUT", "1800")),
        )
    except subprocess.TimeoutExpired:
        raise PipelineError("DEYO_TIMEOUT", "Deyo 链接转写超时，请稍后重试。", "failed")
    transcript = raw_path.read_text(encoding="utf-8", errors="ignore") if raw_path.exists() else (proc.stdout or "")
    transcript = compact_text(transcript, limit=20000)
    if proc.returncode != 0:
        err = compact_text(proc.stderr or proc.stdout or "Deyo 转写失败", limit=1200)
        raise PipelineError("DEYO_TRANSCRIBE_FAILED", err, "failed")
    if content_signal(transcript) < int(os.getenv("MIN_TRANSCRIPT_CHARS", "120")):
        raise PipelineError("DEYO_TRANSCRIPT_TOO_SHORT", "Deyo 未返回足够的视频转写正文，不生成假笔记。", "failed")
    return {
        "platform": infer_platform(link),
        "source_url": clean_link,
        "title": title_hint or clean_link,
        "author": "",
        "cover_url": "",
        "caption_text": title_hint,
        "subtitle_text": transcript,
        "images": [],
        "video_url": "",
        "local_video_path": "",
        "keyframes": [],
        "raw": {"resolver": "deyo", "source": source},
    }


def normalize_tikhub_douyin(link: str, data: dict) -> dict:
    root = data.get("data") or {}
    author = root.get("author") or {}
    video = root.get("video") or {}
    images = root.get("images") or root.get("image_album") or root.get("image_infos") or []
    image_urls = []
    if isinstance(images, list):
        for item in images:
            url = first_url(item)
            if url:
                image_urls.append(url)
    cover = first_url(video.get("cover")) or first_url(video.get("origin_cover")) or (image_urls[0] if image_urls else "")
    play = first_url(deep_get(video, "play_addr", "url_list")) or first_url(deep_get(video, "download_addr", "url_list")) or find_media_url(root)
    return {
        "platform": "抖音",
        "source_url": link,
        "title": root.get("desc") or root.get("item_title") or "未命名抖音作品",
        "author": author.get("nickname") or author.get("unique_id") or "",
        "cover_url": cover,
        "caption_text": root.get("desc") or "",
        "subtitle_text": collect_text(root, ("subtitle", "subtitles", "transcript", "asr", "asr_text", "speech_text", "voice_text")),
        "images": image_urls or ([cover] if cover else []),
        "video_url": play,
        "raw": {**root, "resolver": "tikhub_douyin"},
    }


def normalize_tikhub_xhs(link: str, data: dict) -> dict:
    root = data.get("data") or {}
    user = root.get("user") or root.get("user_info") or {}
    image_list = root.get("image_list") or root.get("images_list") or root.get("images") or []
    image_urls = []
    if isinstance(image_list, list):
        for item in image_list:
            url = first_url(item)
            if url:
                image_urls.append(url)
    video = root.get("video") or root.get("video_info") or {}
    cover = first_url(root.get("cover")) or first_url(video.get("cover")) or (image_urls[0] if image_urls else "")
    play = first_url(video.get("media")) or first_url(video.get("stream")) or first_url(video.get("url")) or first_url(root.get("video_url")) or find_media_url(root)
    desc = root.get("desc") or root.get("content") or root.get("note_desc") or ""
    return {
        "platform": "小红书",
        "source_url": link,
        "title": root.get("title") or desc[:40] or "未命名小红书笔记",
        "author": user.get("nickname") or user.get("name") or user.get("red_id") or "",
        "cover_url": cover,
        "caption_text": desc,
        "subtitle_text": collect_text(root, ("subtitle", "subtitles", "transcript", "asr", "asr_text", "speech_text", "voice_text")),
        "images": image_urls or ([cover] if cover else []),
        "video_url": play,
        "raw": {**root, "resolver": "tikhub_xhs"},
    }


def normalize_tikhub_hybrid(link: str, data: dict) -> dict:
    root = data.get("data") if isinstance(data.get("data"), dict) else data
    author = root.get("author") or root.get("author_info") or root.get("user") or root.get("user_info") or {}
    images = root.get("images") or root.get("image_list") or root.get("image_infos") or []
    image_urls = []
    if isinstance(images, list):
        for item in images:
            url = first_url(item)
            if url:
                image_urls.append(url)
    cover = first_url(root.get("cover")) or first_url(root.get("cover_url")) or (image_urls[0] if image_urls else "")
    desc = root.get("desc") or root.get("title") or root.get("caption") or root.get("content") or ""
    return {
        "platform": root.get("platform") or infer_platform(link),
        "source_url": root.get("source_url") or root.get("url") or link,
        "title": root.get("title") or desc[:40] or "未命名视频笔记",
        "author": author.get("nickname") or author.get("name") or author.get("unique_id") or "",
        "cover_url": cover,
        "caption_text": desc,
        "subtitle_text": collect_text(root, ("subtitle", "subtitles", "transcript", "asr", "asr_text", "speech_text", "voice_text")),
        "images": image_urls or ([cover] if cover else []),
        "video_url": find_media_url(root),
        "raw": {**root, "resolver": "tikhub_hybrid"},
    }


def resolve_with_tikhub(link: str) -> dict:
    clean_link = extract_share_url(link)
    api_key = os.getenv("TIKHUB_API_KEY", "").strip()
    if not api_key:
        raise PipelineError("TIKHUB_NOT_CONFIGURED", "未配置 TIKHUB_API_KEY")
    base = os.getenv("TIKHUB_BASE_URL", "https://api.tikhub.io").rstrip("/")
    timeout = int(os.getenv("TIKHUB_TIMEOUT", "25"))
    platform = infer_platform(link)
    hybrid_errors = []
    try:
        data = http_get_json(
            f"{base}/api/v1/hybrid/video_data",
            {"url": clean_link, "minimal": "false", "base64_url": "false"},
            api_key,
            timeout,
        )
        if data.get("code") in [0, 200, "0", "200", None] and data.get("data"):
            return normalize_tikhub_hybrid(clean_link, data)
        hybrid_errors.append(data.get("message_zh") or data.get("message") or "hybrid/video_data")
    except urllib.error.HTTPError as exc:
        hybrid_errors.append(format_tikhub_http_error(exc, "/api/v1/hybrid/video_data"))
    except Exception as exc:
        hybrid_errors.append(str(exc))
    if platform == "抖音":
        errors = hybrid_errors[:]
        for path in [
            "/api/v1/douyin/app/v3/fetch_one_video_by_share_url",
            "/api/v1/douyin/web/fetch_one_video_by_share_url",
        ]:
            try:
                endpoint = f"{base}{path}"
                data = http_get_json(endpoint, {"share_url": clean_link}, api_key, timeout)
                if data.get("code") in [0, 200, "0", "200", None] and data.get("data"):
                    return normalize_tikhub_douyin(clean_link, data)
                errors.append(data.get("message_zh") or data.get("message") or path)
            except urllib.error.HTTPError as exc:
                errors.append(format_tikhub_http_error(exc, path))
            except Exception as exc:
                errors.append(str(exc))
        raise PipelineError("TIKHUB_DOUYIN_FAILED", "抖音解析失败：" + "；".join(errors[:3]))
    if platform == "小红书":
        errors = hybrid_errors[:]
        for path in ["get_video_note_detail", "get_image_note_detail"]:
            for share_text in dict.fromkeys([link, clean_link]):
                try:
                    endpoint = f"{base}/api/v1/xiaohongshu/app_v2/{path}"
                    data = http_get_json(endpoint, {"share_text": share_text}, api_key, timeout)
                    if data.get("code") in [0, 200, "0", "200", None] and data.get("data"):
                        return normalize_tikhub_xhs(clean_link, data)
                    errors.append(data.get("message_zh") or data.get("message") or path)
                    break
                except urllib.error.HTTPError as exc:
                    errors.append(format_tikhub_http_error(exc, f"/api/v1/xiaohongshu/app_v2/{path}"))
                    if exc.code in [401, 403, 444]:
                        break
                except Exception as exc:
                    errors.append(str(exc))
        raise PipelineError("TIKHUB_XHS_FAILED", "小红书解析失败：" + "；".join(errors[:2]))
    raise PipelineError("UNSUPPORTED_PLATFORM", "仅支持抖音/小红书链接", "need_upload")


def resolve_media_with_ytdlp(link: str) -> str:
    try:
        import yt_dlp
    except ImportError:
        return ""
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(extract_share_url(link), download=False)
    except Exception:
        return ""
    formats = [item for item in (info.get("formats") or []) if item.get("url") and item.get("vcodec") != "none"]
    if formats:
        formats.sort(key=lambda item: (int(item.get("height") or 0), float(item.get("tbr") or 0)), reverse=True)
        return str(formats[0]["url"])
    return str(info.get("url") or "")


def resolve_link(link: str) -> dict:
    supported_platform = infer_platform(link) in ["抖音", "小红书"]
    if supported_platform and os.getenv("DEYO_ENABLED", "1") == "1":
        try:
            return resolve_with_deyo(link)
        except PipelineError as exc:
            if os.getenv("STRICT_DEYO_PARSE", "0") == "1":
                raise
            first_deyo_error = exc
    if supported_platform and os.getenv("REAL_VIDEO_FIRST", "1") == "1" and os.getenv("CRV_ENABLED", "1") == "1":
        try:
            return resolve_with_crv(link)
        except PipelineError as exc:
            if os.getenv("STRICT_CRV_FIRST", "0") == "1":
                raise
            if "first_deyo_error" in locals() and os.getenv("PREFER_DEYO_ERROR", "0") == "1":
                raise first_deyo_error
            first_crv_error = exc
    if os.getenv("TIKHUB_API_KEY", "").strip():
        try:
            return resolve_with_tikhub(link)
        except PipelineError as exc:
            if supported_platform or os.getenv("STRICT_TIKHUB_PARSE", "0") == "1":
                if os.getenv("CRV_ENABLED", "1") == "1":
                    try:
                        return resolve_with_crv(link)
                    except PipelineError:
                        if "first_crv_error" in locals():
                            raise first_crv_error
                        raise
                raise
        except Exception as exc:
            if supported_platform or os.getenv("STRICT_TIKHUB_PARSE", "0") == "1":
                if os.getenv("CRV_ENABLED", "1") == "1":
                    try:
                        return resolve_with_crv(link)
                    except PipelineError:
                        if "first_crv_error" in locals():
                            raise first_crv_error
                        raise
                raise PipelineError("TIKHUB_PARSE_FAILED", f"TikHub解析失败：{exc}", "need_upload")
    parser_url = os.getenv("THIRD_PARTY_PARSE_URL", "").strip()
    parser_token = os.getenv("THIRD_PARTY_PARSE_TOKEN", "").strip()
    if parser_url:
        try:
            data = http_json(parser_url, {"url": extract_share_url(link), "share_text": link}, parser_token)
            parsed = normalize_parser_result(extract_share_url(link), data)
            parsed["raw"]["resolver"] = "third_party"
            return parsed
        except Exception as exc:
            if os.getenv("STRICT_THIRD_PARTY_PARSE", "0") == "1":
                raise PipelineError("THIRD_PARTY_PARSE_FAILED", f"第三方解析失败：{exc}", "need_upload")
    if supported_platform:
        if os.getenv("CRV_ENABLED", "1") == "1":
            return resolve_with_crv(link)
        raise PipelineError("REAL_PARSER_REQUIRED", "抖音/小红书必须接入真实解析接口后才能生成笔记，禁止只读标题和网页标签生成假笔记。", "failed")
    return fetch_public_meta(link)


def download_file(url: str, suffix: str = ".mp4") -> str:
    if not url:
        return ""
    max_mb = int(os.getenv("MAX_MEDIA_DOWNLOAD_MB", "80"))
    target = Path(tempfile.gettempdir()) / f"vkb-{hashlib.md5(url.encode()).hexdigest()}{suffix}"
    if target.exists():
        return str(target)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, target.open("wb") as f:
            size = 0
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_mb * 1024 * 1024:
                    raise PipelineError("MEDIA_TOO_LARGE", "视频文件过大，请上传压缩后的视频", "need_upload")
                f.write(chunk)
    except urllib.error.HTTPError as exc:
        raise PipelineError("MEDIA_DOWNLOAD_FAILED", format_tikhub_http_error(exc, "视频媒体地址"), "need_upload")
    return str(target)


def find_ffmpeg() -> str:
    configured = os.getenv("FFMPEG_CLI", "").strip()
    if configured and Path(configured).exists():
        return configured
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return ""


def transcribe_audio(video_url: str = "", local_path: str = "") -> str:
    if not video_url and not local_path:
        return ""
    media = local_path or download_file(video_url)
    if not media:
        return ""

    try:
        from faster_whisper import WhisperModel
        model_name = os.getenv("WHISPER_MODEL", "small")
        model = WhisperModel(model_name, device=os.getenv("WHISPER_DEVICE", "cpu"), compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
        segments, _ = model.transcribe(media, language="zh", vad_filter=True)
        return "\n".join(seg.text.strip() for seg in segments if seg.text.strip())
    except ImportError:
        pass
    except Exception as exc:
        raise PipelineError("ASR_FAILED", f"已拿到视频地址，但本地音频转写失败：{exc}。通常是解析接口返回的不是可播放视频文件。", "need_upload")

    cli = os.getenv("WHISPER_CLI", "").strip()
    if cli:
        out_dir = tempfile.mkdtemp(prefix="vkb-whisper-")
        subprocess.run([cli, media, "--language", "Chinese", "--model", os.getenv("WHISPER_MODEL", "small"), "--output_format", "txt", "--output_dir", out_dir], check=True, timeout=900)
        txt_files = list(Path(out_dir).glob("*.txt"))
        return txt_files[0].read_text(encoding="utf-8", errors="ignore") if txt_files else ""
    raise PipelineError("ASR_NOT_AVAILABLE", "视频没有可用字幕，且本地 Whisper 未安装；必须安装 faster-whisper 或配置 WHISPER_CLI 后才能解析视频音频。")


def ocr_keyframes(video_url: str = "", local_path: str = "") -> tuple[str, list[str]]:
    if not video_url and not local_path:
        return "", []
    if not importlib.util.find_spec("paddleocr") and not importlib.util.find_spec("rapidocr_onnxruntime"):
        return "", []
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return "", []

    media = local_path or download_file(video_url)
    out_dir = Path(tempfile.mkdtemp(prefix="vkb-frames-"))
    fps = os.getenv("KEYFRAME_FPS", "1/5")
    subprocess.run([ffmpeg, "-y", "-i", media, "-vf", f"fps={fps},scale=640:-1", str(out_dir / "frame-%03d.jpg")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    frames = sorted(out_dir.glob("*.jpg"))[: int(os.getenv("MAX_KEYFRAMES", "8"))]
    if not frames:
        return "", []
    frame_paths = [str(x) for x in frames]
    return ocr_existing_frames(frame_paths), frame_paths


def ocr_existing_frames(frames: list[str]) -> str:
    frames = [str(x) for x in frames if x and Path(str(x)).exists()][: int(os.getenv("OCR_MAX_KEYFRAMES", os.getenv("MAX_KEYFRAMES", "12")))]
    if not frames or os.getenv("VISUAL_OCR_ENABLED", "1") != "1":
        return ""
    texts = []
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        for frame in frames:
            result, _ = engine(frame)
            for item in result or []:
                if len(item) >= 2 and str(item[1]).strip():
                    texts.append(str(item[1]).strip())
        return "\n".join(dict.fromkeys(texts))
    except ImportError:
        pass
    except Exception:
        pass
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        for frame in frames:
            result = ocr.ocr(frame, cls=True)
            for line in result[0] if result else []:
                if line and len(line) > 1 and line[1][0]:
                    texts.append(line[1][0])
    except ImportError:
        return ""
    except Exception:
        return ""
    return "\n".join(dict.fromkeys(texts))


def compact_text(*parts: str, limit: int = 9000) -> str:
    text = "\n".join(p.strip() for p in parts if p and p.strip())
    text = re.sub(r"(关注|点赞|评论|私信|橱窗|下单|直播间|领券|戳链接)[^\n。]{0,40}", "", text)
    text = re.sub(r"小红书[_｜|].{0,30}(ICP备|营业执照|公网安备|举报中心|许可证)[^\n。]{0,60}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def content_signal(text: str) -> int:
    if not text:
        return 0
    clean = re.sub(r"#([^#\n]{1,30})(\[话题\])?#", "", text)
    clean = re.sub(r"(小红书|抖音|ICP备|营业执照|公网安备|举报中心|互联网药品信息服务|3 亿人的生活经验)", "", clean)
    clean = re.sub(r"\s+", "", clean)
    return len(clean)


def validate_payload(payload: dict, link: str = ""):
    if payload.get("prompt_version") != PROMPT_VERSION:
        raise PipelineError("BAD_CACHE_PROMPT_VERSION", "缓存结果使用旧版笔记 Prompt，已拒绝复用。")
    source = payload.get("source") or {}
    video_mode = is_video_source(source, link)
    transcript = compact_text(payload.get("transcript", "") or source.get("subtitle_text", ""), limit=20000)
    evidence = compact_text(transcript, source.get("caption_text", ""), payload.get("ocr_text", ""))
    if video_mode and content_signal(transcript) < int(os.getenv("MIN_TRANSCRIPT_CHARS", "120")):
        raise PipelineError("BAD_CACHE_TRANSCRIPT", "缓存结果缺少完整视频字幕/音频转写，已拒绝复用。")
    if content_signal(evidence) < int(os.getenv("MIN_EVIDENCE_CHARS", "80")):
        raise PipelineError("BAD_CACHE_EVIDENCE", "缓存结果缺少有效正文证据，已拒绝复用。")
    try:
        payload["note"] = normalize_analysis_result(payload.get("note"))
    except ValueError as exc:
        raise PipelineError("BAD_ANALYSIS_SCHEMA", f"AI 拆解结果不符合固定 JSON 规范：{exc}")


def normalize_analysis_result(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("顶层必须是 JSON 对象")
    required = {"video_type", "core_points", "action_steps", "highlights", "extra_info"}
    missing = required.difference(value)
    if missing:
        raise ValueError("缺少字段：" + "、".join(sorted(missing)))

    video_type = str(value.get("video_type") or "").strip().strip("【】")
    if video_type not in VIDEO_TYPES:
        raise ValueError("video_type 必须是五种固定分类之一")

    normalized = {"video_type": video_type}
    for key in ["core_points", "action_steps", "highlights"]:
        items = value.get(key)
        if not isinstance(items, list):
            raise ValueError(f"{key} 必须是数组")
        normalized[key] = [str(item).strip() for item in items if str(item).strip()]

    extra = value.get("extra_info")
    if not isinstance(extra, dict):
        raise ValueError("extra_info 必须是对象")
    extra_fields = ["product_info", "event_timeline", "story_intro"]
    missing_extra = [key for key in extra_fields if key not in extra]
    if missing_extra:
        raise ValueError("extra_info 缺少字段：" + "、".join(missing_extra))
    normalized["extra_info"] = {key: str(extra.get(key) or "").strip() for key in extra_fields}
    if video_type != "带货种草类" and normalized["extra_info"]["product_info"]:
        raise ValueError("非带货种草类的 product_info 必须为空字符串")
    if video_type != "资讯热点类" and normalized["extra_info"]["event_timeline"]:
        raise ValueError("非资讯热点类的 event_timeline 必须为空字符串")
    if video_type not in {"闲聊Vlog类", "影视解说类"} and normalized["extra_info"]["story_intro"]:
        raise ValueError("非闲聊Vlog/影视解说类的 story_intro 必须为空字符串")
    return normalized


def prompt_for_note(source: dict, merged_text: str) -> str:
    return f"""# 任务规则
你是短视频知识库解析引擎，只基于提供的视频内容完成分析，严禁编造视频不存在的信息。
硬性约束：
1. 最终视频类型五选一，只能输出下面其中一项：【知识干货类】/【带货种草类】/【闲聊Vlog类】/【资讯热点类】/【影视解说类】，不能多选、不能自定义分类；
2. 严格按照对应分类规则拆解内容；
3. 仅返回纯净标准JSON，不要任何额外解释、开场白、注释；
4. 无内容统一使用空字符串""、空数组[]，禁止删除字段。

执行流程：
第一步：自动判定视频所属类型（五选一）
第二步：根据判定结果，启用对应专属拆解规则
第三步：输出JSON

## 分类拆解规则
1.【知识干货类】（教程、认知分享、方法论、行业科普、学习干货）
重点抽取：核心原理、关键结论、避坑要点、可复用知识点、金句

2.【带货种草类】（产品测评、好物推荐、团购、广告、种草）
重点抽取：产品名称、核心卖点、优缺点、适用人群、价格、使用场景

3.【闲聊Vlog类】（日常记录、个人感悟、叙事故事、情绪分享，无干货无商品无热点）
重点抽取：主线故事、核心情绪、感悟观点、关键事件

4.【资讯热点类】（热点事件、新闻快讯、行业动态、事件复盘、时事解读）
重点抽取：事件概况、关键时间线、各方观点、事件影响

5.【影视解说类】（电影、剧集、动漫解说、剧情梳理、角色点评）
重点抽取：剧情梗概、核心冲突、人物介绍、作品主旨、经典台词

## JSON固定输出字段规范
{{
  "video_type": "只能填写上面5个分类名称",
  "core_points": ["多条核心信息清单"],
  "action_steps": ["可落地操作步骤，无则为空数组"],
  "highlights": ["高价值原文摘录，无则为空数组"],
  "extra_info": {{
    "product_info": "仅带货类填写产品相关信息，其他类型填空字符串",
    "event_timeline": "仅资讯热点类填写事件时间线，其他类型填空字符串",
    "story_intro": "仅闲聊Vlog/影视解说填写剧情/故事简述，其他类型填空字符串"
  }}
}}

## 待分析视频内容
来源：{source.get('platform')}｜{source.get('author')}
标题：{source.get('title')}
视频完整内容：
{merged_text}"""


def call_llm(source: dict, merged_text: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LOW_COST_TEXT_MODEL", "deepseek-chat")
    if api_key:
        errors = []
        fallback_models = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "deepseek-chat").split(",") if m.strip()]
        models = list(dict.fromkeys([model, *fallback_models]))
        for current_model in models:
            try:
                payload = {
                    "model": current_model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt_for_note(source, merged_text)}],
                }
                data = http_json(f"{base}/chat/completions", payload, api_key, timeout=90)
                content = data["choices"][0]["message"]["content"]
                return normalize_analysis_result(json.loads(content))
            except Exception as exc:
                errors.append(f"{current_model}: {safe_error_text(exc)}")
        if os.getenv("LLM_FALLBACK_ON_ERROR", "0") != "1" or os.getenv("STRICT_LLM", "0") == "1":
            raise PipelineError("LLM_CALL_FAILED", "大模型生成失败：" + "；".join(errors[-3:]))
    return heuristic_note(source, merged_text)


def heuristic_note(source: dict, merged_text: str) -> dict:
    title = source.get("title") or ""
    text = merged_text or source.get("caption_text") or title or ""
    if title and text.startswith(title):
        text = text[len(title):].strip()
    sentences = [x.strip() for x in re.split(r"[。！？\n]", text) if len(x.strip()) > 6]
    picked = sentences[:5] or ["当前链接未取得足够正文，系统不会只根据标题生成假笔记。"]
    product_words = ["产品", "价格", "购买", "推荐", "测评", "好物", "优惠", "团购", "种草"]
    film_words = ["电影", "电视剧", "动漫", "剧情", "角色", "导演", "演员"]
    news_words = ["新闻", "热点", "事件", "发布", "通报", "行业动态", "最新消息"]
    vlog_words = ["今天", "日常", "生活", "记录", "心情", "感受", "旅行", "下班"]
    if any(word in text for word in product_words):
        video_type = "带货种草类"
    elif any(word in text for word in film_words):
        video_type = "影视解说类"
    elif any(word in text for word in news_words):
        video_type = "资讯热点类"
    elif any(word in text for word in vlog_words):
        video_type = "闲聊Vlog类"
    else:
        video_type = "知识干货类"
    action_steps = [item for item in picked if re.search(r"(先|再|然后|步骤|点击|打开|设置|选择|使用|将)", item)]
    return {
        "video_type": video_type,
        "core_points": picked,
        "action_steps": action_steps,
        "highlights": picked[:2],
        "extra_info": {
            "product_info": picked[0] if video_type == "带货种草类" else "",
            "event_timeline": picked[0] if video_type == "资讯热点类" else "",
            "story_intro": picked[0] if video_type in {"闲聊Vlog类", "影视解说类"} else "",
        },
    }


def run_pipeline(link: str, progress=None) -> dict:
    def emit(stage: str, message: str):
        if callable(progress):
            progress(stage, message)

    emit("resolving_link", "正在识别平台并解析视频链接")
    if infer_platform(link) in ["抖音", "小红书"] and os.getenv("DEYO_ENABLED", "1") == "1" and find_deyo_cli():
        emit("transcribing_audio", "Deyo 正在获取并转写视频正文")
    source = resolve_link(link)
    emit("source_ready", "视频链接解析完成，正在获取正文内容")
    def switch_to_crv(reason: str):
        if infer_platform(link) in ["抖音", "小红书"] and os.getenv("CRV_ENABLED", "1") == "1" and (source.get("raw") or {}).get("resolver") != "claude_real_video":
            emit("downloading_video", "备用解析通道正在下载并读取真实视频")
            return resolve_with_crv(link)
        raise PipelineError("LINK_VIDEO_PARSE_FAILED", reason, "failed")

    video_mode = is_video_source(source, link)
    transcript = compact_text(source.get("subtitle_text", ""), limit=20000)
    if video_mode:
        if not transcript:
            if not source.get("video_url"):
                source = switch_to_crv("解析接口没有返回可转写的视频地址或字幕，且 CRV 兜底解析失败。")
                transcript = compact_text(source.get("subtitle_text", ""), limit=20000)
            else:
                try:
                    emit("transcribing_audio", "正在转写视频音频，较长视频需要等待几分钟")
                    transcript = transcribe_audio(video_url=source["video_url"])
                except PipelineError as exc:
                    source = switch_to_crv(f"TikHub 返回的视频媒体不可转写，CRV 兜底解析失败：{exc.message}")
                    transcript = compact_text(source.get("subtitle_text", ""), limit=20000)
            video_mode = is_video_source(source, link)
        if content_signal(transcript) < int(os.getenv("MIN_TRANSCRIPT_CHARS", "120")):
            source = switch_to_crv("视频转写内容过短，且 CRV 兜底解析未能取得足够正文。")
            transcript = compact_text(source.get("subtitle_text", ""), limit=20000)
            if content_signal(transcript) < int(os.getenv("MIN_TRANSCRIPT_CHARS", "120")):
                raise PipelineError("TRANSCRIPT_TOO_SHORT", "视频转写内容过短，未达到生成知识笔记标准；不生成假笔记。", "failed")
    ocr_text, frames = ("", [])
    if source.get("video_url"):
        emit("extracting_visual_text", "正在识别视频关键画面文字")
        ocr_text, frames = ocr_keyframes(video_url=source["video_url"])
    if not frames and source.get("keyframes"):
        frames = source.get("keyframes", [])
    if not frames and infer_platform(link) in ["抖音", "小红书"] and os.getenv("VISUAL_OCR_ENABLED", "1") == "1" and os.getenv("TIKHUB_API_KEY", "").strip():
        try:
            emit("extracting_visual_text", "正在通过备用媒体通道提取视频关键画面")
            visual_source = resolve_with_tikhub(link)
            if visual_source.get("video_url"):
                ocr_text, frames = ocr_keyframes(video_url=visual_source["video_url"])
        except (PipelineError, OSError, RuntimeError):
            pass
    if not frames and infer_platform(link) in ["抖音", "小红书"] and os.getenv("VISUAL_OCR_ENABLED", "1") == "1":
        media_url = resolve_media_with_ytdlp(link)
        if media_url:
            emit("extracting_visual_text", "正在通过公开媒体通道提取视频关键画面")
            ocr_text, frames = ocr_keyframes(video_url=media_url)
    if not frames and infer_platform(link) in ["抖音", "小红书"] and os.getenv("VISUAL_OCR_ENABLED", "1") == "1":
        frames = extract_keyframes_with_crv(link)
    if frames and not ocr_text:
        ocr_text = ocr_existing_frames(frames)
    evidence_text = compact_text(transcript, source.get("caption_text", ""), ocr_text)
    if content_signal(evidence_text) < int(os.getenv("MIN_EVIDENCE_CHARS", "80")):
        resolver = (source.get("raw") or {}).get("resolver", "")
        if resolver == "public_meta":
            source = switch_to_crv("只读取到网页标题/标签，CRV 兜底解析也未取得足够正文。")
            transcript = compact_text(source.get("subtitle_text", ""), limit=20000)
            ocr_text, frames = ("", source.get("keyframes", []))
            evidence_text = compact_text(transcript, source.get("caption_text", ""), ocr_text)
        if content_signal(evidence_text) < int(os.getenv("MIN_EVIDENCE_CHARS", "80")):
            raise PipelineError("NO_VIDEO_CONTENT", "链接解析未返回足够的视频正文/字幕/图文内容，不生成假笔记。", "failed")
    merged = compact_text(
        source.get("title", ""),
        "【口播/字幕转写】\n" + transcript if transcript else "",
        "【画面文字OCR】\n" + ocr_text if ocr_text else "",
        source.get("caption_text", ""),
    )
    emit("generating_note", "正文提取完成，AI 正在生成结构化知识笔记")
    payload = {
        "source": source,
        "transcript": transcript,
        "ocr_text": ocr_text,
        "keyframes": frames[: int(os.getenv("MAX_KEYFRAMES", "8"))],
        "merged_text": merged,
        "note": call_llm(source, merged),
        "prompt_version": PROMPT_VERSION,
        "cost": {"cacheable": True, "llm_input_chars": len(merged), "used_local_asr": bool(transcript and not source.get("subtitle_text"))},
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    emit("validating_note", "正在校验笔记质量并保存到知识库")
    validate_payload(payload, link)
    return payload
