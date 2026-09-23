from __future__ import annotations
import base64, hashlib, hmac, importlib.util, json, mimetypes, os, re, secrets, shutil, sqlite3, threading, time, uuid, zipfile
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pipeline import PipelineError, find_deyo_cli, find_ffmpeg, link_key, run_pipeline, validate_payload

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    hashes = serialization = padding = AESGCM = None

DB = Path(os.getenv("VIDEO_KNOWLEDGE_DB", str(Path(__file__).resolve().parent / "video_knowledge.db")))
EXPORT_DIR = Path(os.getenv("VIDEO_KNOWLEDGE_EXPORT_DIR", str(Path(__file__).resolve().parent / "exports")))
HOST = os.getenv("VIDEO_KNOWLEDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("VIDEO_KNOWLEDGE_PORT") or os.getenv("PORT") or "8787")
H5_DIST_DIR = Path(os.getenv("H5_DIST_DIR", str(Path(__file__).resolve().parent.parent / "dist" / "build" / "h5")))
SERVE_H5 = os.getenv("SERVE_H5", "0") == "1"

PLAN_CONFIG = {
    "monthly": {"name": "月度VIP", "amount": 2900, "quota": 300, "member_type": "月度VIP"},
    "yearly": {"name": "年度VIP", "amount": 19900, "quota": 5000, "member_type": "年度VIP"},
}

def payment_enabled():
    return os.getenv("PAYMENT_ENABLED", "0").strip() == "1"

def free_beta_quota():
    try:
        return max(1, int(os.getenv("FREE_BETA_QUOTA", "20")))
    except ValueError:
        return 20

def public_demo_mode():
    return os.getenv("PUBLIC_DEMO_MODE", "0") == "1"

def public_demo_daily_limit():
    try:
        return max(1, int(os.getenv("PUBLIC_DEMO_DAILY_LIMIT", "20")))
    except ValueError:
        return 20

def api_path(raw_path):
    if raw_path == "/backend":
        return "/"
    if raw_path.startswith("/backend/"):
        return raw_path[len("/backend"):]
    return raw_path

def load_env():
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_file.exists(): return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
def config_value(name, default=""):
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, item = line.split("=", 1)
            if key.strip() == name and item.strip():
                return item.strip()
    return default
def public_api_base():
    configured = config_value("PUBLIC_API_BASE_URL", "").rstrip("/")
    if configured:
        return configured
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if render_url:
        return render_url + "/backend"
    return f"http://{HOST}:{PORT}"

def now(): return time.strftime("%Y-%m-%d %H:%M:%S")
def conn():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row; return c
def j(data): return json.dumps(data, ensure_ascii=False).encode("utf-8")
def body(h):
    n = int(h.headers.get("content-length", 0)); return json.loads(h.rfile.read(n).decode("utf-8") or "{}") if n else {}
def token(): return uuid.uuid4().hex
def hash_password(password):
    iterations = 210000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
def verify_password(password, stored):
    stored = str(stored or "")
    if not stored.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(str(password), stored)
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$", 3)
        actual = hashlib.pbkdf2_hmac(
            "sha256", str(password).encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (TypeError, ValueError):
        return False
def note_row(r):
    d = dict(r)
    for k in ["tags","steps","terms","cases","extension","annotations"]:
        d[k] = json.loads(d[k] or "{}" if k in ["cases","extension","annotations"] else d[k] or "[]")
    return d
def safe_name(name):
    return re.sub(r"[\\/:*?\"<>|\r\n]+", "_", str(name or "note")).strip(" .")[:80] or "note"
def looks_corrupt_text(value):
    text = str(value or "").strip()
    if not text:
        return False
    if re.search(r"(ï¿½|锟斤拷|�|鏂|瑙|绗|灏|鎶|鐭|銆|锛|鈥)", text):
        return True
    question_runs = sum(len(x) for x in re.findall(r"\?{2,}", text))
    return question_runs >= 3 or question_runs / max(len(text), 1) > 0.06
def assert_note_quality(n):
    fields = ["title", "summary", "theory", "author", "category", "sub_category"]
    if any(looks_corrupt_text(n.get(k)) for k in fields):
        raise PipelineError("NOTE_TEXT_CORRUPT", "解析结果出现乱码或问号占位，已拒绝生成笔记，请重新解析。", "failed")
    title = str(n.get("title") or "").strip()
    summary = str(n.get("summary") or "").strip()
    theory = str(n.get("theory") or "").strip()
    if title.startswith(("http://", "https://")) or summary.startswith(("http://", "https://")) or theory.startswith(("http://", "https://")):
        raise PipelineError("NOTE_ONLY_LINK", "解析结果只有链接或标题，没有取得视频正文，已拒绝生成笔记。", "failed")
    if theory in [title, summary] or len(theory) < 80:
        raise PipelineError("NOTE_TOO_SHORT", "结构化笔记内容过短，未达到入库标准。", "failed")
def xml_escape(text):
    return str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def note_markdown(n):
    tags = n.get("tags") or []
    annotations = n.get("annotations") or {}
    parts = [
        f"# {n.get('title') or '未命名笔记'}",
        "",
        f"- 平台：{n.get('platform') or ''}",
        f"- 作者：{n.get('author') or ''}",
        f"- 知识大类：{n.get('category') or ''}",
        f"- 细分小类：{n.get('sub_category') or ''}",
        f"- 标签：{'、'.join(tags)}",
        f"- 原始链接：{n.get('source_url') or ''}",
        "",
        "## 内容摘要",
        n.get("summary") or "",
        "",
        "## 核心知识点拆解",
        n.get("theory") or "",
    ]
    if n.get("quote"):
        parts += ["", "## 金句摘录", f"> {n.get('quote')}"]
    manual = [annotations.get("highlight"), annotations.get("question"), annotations.get("transfer"), annotations.get("memory")]
    extra = annotations.get("extra") or []
    if any(manual) or extra:
        parts += ["", "## 个人学习批注"]
        labels = ["重点标记", "疑问点", "举一反三", "记忆简化总结"]
        for label, value in zip(labels, manual):
            if value: parts += [f"### {label}", value]
        for item in extra:
            if item: parts += ["### 新增批注", item]
    return "\n".join(parts).strip() + "\n"
def write_markdown_export(notes, prefix="notes"):
    EXPORT_DIR.mkdir(exist_ok=True)
    filename = f"{safe_name(prefix)}-{time.strftime('%Y%m%d-%H%M%S')}.md"
    path = EXPORT_DIR / filename
    text = "\n\n---\n\n".join(note_markdown(n) for n in notes)
    path.write_text(text, encoding="utf-8")
    return filename, path
def write_docx_export(notes, prefix="notes"):
    EXPORT_DIR.mkdir(exist_ok=True)
    filename = f"{safe_name(prefix)}-{time.strftime('%Y%m%d-%H%M%S')}.docx"
    path = EXPORT_DIR / filename
    paragraphs = []
    for n in notes:
        for line in note_markdown(n).splitlines():
            style = ' w:val="Heading1"' if line.startswith("# ") else ' w:val="Heading2"' if line.startswith("## ") else ""
            text = re.sub(r"^#+\s*", "", line)
            paragraphs.append(f"<w:p><w:pPr>{'<w:pStyle'+style+'/>' if style else ''}</w:pPr><w:r><w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>")
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>""" + "".join(paragraphs) + "<w:sectPr/></w:body></w:document>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        z.writestr("word/document.xml", document)
    return filename, path
def load_export_notes(c, user_id, ids):
    ids = [x for x in (ids or []) if isinstance(x, str) and x.strip()]
    if ids:
        marks = ",".join("?" for _ in ids)
        rows = c.execute(f"SELECT * FROM notes WHERE user_id=? AND archived=0 AND id IN ({marks})", [user_id] + ids).fetchall()
    else:
        rows = c.execute("SELECT * FROM notes WHERE user_id=? AND archived=0 ORDER BY updated_at DESC", (user_id,)).fetchall()
    return [note_row(r) for r in rows]
def json_request(url, payload=None, headers=None, method=None, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method or ("POST" if data is not None else "GET"))
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items(): req.add_header(k, str(v))
    with urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw or "{}")
def form_request(url, payload, headers=None, timeout=30):
    data = urlencode(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for k, v in (headers or {}).items(): req.add_header(k, str(v))
    with urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw or "{}")
def multipart_request(url, fields, file_field, file_path, headers=None, timeout=120):
    boundary = "----VideoKnowledge" + uuid.uuid4().hex
    body_parts = []
    for name, value in fields.items():
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    file_name = Path(file_path).name
    body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_name}\"\r\nContent-Type: text/markdown\r\n\r\n".encode("utf-8"))
    body_parts.append(Path(file_path).read_bytes())
    body_parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    data = b"".join(body_parts)
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(data)))
    for k, v in (headers or {}).items(): req.add_header(k, str(v))
    try:
        with urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw or "{}")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            error = json.loads(raw or "{}")
            detail = error.get("msg") or error.get("message") or raw
        except json.JSONDecodeError:
            detail = raw
        raise RuntimeError(f"文件上传失败（HTTP {exc.code}）：{detail}") from exc
def integration_row(c, user_id, provider):
    return c.execute("SELECT * FROM integrations WHERE user_id=? AND provider=?", (user_id, provider)).fetchone()
def upsert_integration(c, user_id, provider, token_data):
    expires_in = int(token_data.get("expires_in") or token_data.get("expiresIn") or 0)
    expires_at = int(time.time()) + expires_in if expires_in else 0
    c.execute("""INSERT OR REPLACE INTO integrations(user_id,provider,access_token,refresh_token,expires_at,meta,updated_at)
        VALUES(?,?,?,?,?,?,?)""", (user_id, provider, token_data.get("access_token") or token_data.get("user_access_token") or "", token_data.get("refresh_token") or "", expires_at, json.dumps(token_data, ensure_ascii=False), now()))
def refresh_integration(c, user_id, provider, row):
    refresh_token = row["refresh_token"] if row else ""
    if not refresh_token:
        raise RuntimeError(f"{provider.upper()} 授权已过期，请重新授权")
    if provider != "feishu":
        raise RuntimeError("该云端集成已停用")
    payload = {
        "grant_type": "refresh_token",
        "client_id": os.getenv("FEISHU_APP_ID", ""),
        "client_secret": os.getenv("FEISHU_APP_SECRET", ""),
        "refresh_token": refresh_token,
    }
    data = json_request(os.getenv("FEISHU_TOKEN_URL", "https://open.feishu.cn/open-apis/authen/v2/oauth/token"), payload)
    if data.get("code") not in (None, 0):
        raise RuntimeError(data.get("msg") or "飞书授权刷新失败")
    token_data = data.get("data") or data
    if not token_data.get("refresh_token"):
        token_data["refresh_token"] = refresh_token
    upsert_integration(c, user_id, provider, token_data)
    return integration_row(c, user_id, provider)
def integration_access_token(c, user_id, provider):
    row = integration_row(c, user_id, provider)
    if not row or not row["access_token"]:
        raise RuntimeError("请先在个人中心完成飞书授权")
    if row["expires_at"] and row["expires_at"] <= int(time.time()) + 60:
        row = refresh_integration(c, user_id, provider, row)
    return row["access_token"]
def oauth_redirect_url(provider):
    return config_value(f"{provider.upper()}_REDIRECT_URI", f"http://{HOST}:{PORT}/api/oauth/{provider}/callback")
def frontend_done_url(provider, ok=True):
    h5 = config_value("H5_BASE_URL", "http://127.0.0.1:8088")
    return f"{h5}/#/pages/mine/mine?oauth={provider}&ok={'1' if ok else '0'}"
def feishu_auth_url(state):
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    if not app_id: raise ValueError("缺少 FEISHU_APP_ID")
    base = os.getenv("FEISHU_AUTH_URL", "https://accounts.feishu.cn/open-apis/authen/v1/authorize")
    params = {"app_id": app_id, "redirect_uri": oauth_redirect_url("feishu"), "state": state}
    scope = (os.getenv("FEISHU_SCOPE") or "drive:file:upload").strip()
    if scope:
        params["scope"] = scope
    return f"{base}?{urlencode(params)}"
def exchange_feishu_code(code):
    payload = {"grant_type": "authorization_code", "client_id": os.getenv("FEISHU_APP_ID", ""), "client_secret": os.getenv("FEISHU_APP_SECRET", ""), "code": code, "redirect_uri": oauth_redirect_url("feishu")}
    data = json_request(os.getenv("FEISHU_TOKEN_URL", "https://open.feishu.cn/open-apis/authen/v2/oauth/token"), payload)
    if data.get("code") not in (None, 0):
        raise RuntimeError(data.get("msg") or data.get("message") or "飞书授权失败")
    return data.get("data") or data
def normalize_feishu_parent_node(value):
    node = str(value or "").strip()
    if node.startswith(("http://", "https://")):
        match = re.search(r"/drive/folder/([^/?#]+)", urlparse(node).path)
        if match:
            return match.group(1)
    return node
def sync_to_feishu(c, user_id, notes):
    access_token = integration_access_token(c, user_id, "feishu")
    filename, path = write_markdown_export(notes, "feishu-sync")
    parent_type = os.getenv("FEISHU_PARENT_TYPE", "explorer")
    parent_node = normalize_feishu_parent_node(os.getenv("FEISHU_PARENT_NODE", ""))
    if not parent_node:
        raise RuntimeError("缺少 FEISHU_PARENT_NODE：请在飞书云空间选择目标文件夹并配置其 token")
    res = multipart_request(
        os.getenv("FEISHU_UPLOAD_URL", "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"),
        {"file_name": filename, "parent_type": parent_type, "parent_node": parent_node, "size": path.stat().st_size},
        "file", path, {"Authorization": "Bearer " + access_token},
    )
    if res.get("code") not in (None, 0):
        raise RuntimeError(res.get("msg") or "飞书上传失败")
    data = res.get("data") or {}
    file_token = str(data.get("file_token") or data.get("token") or "").strip()
    if not file_token:
        raise RuntimeError("飞书接口返回成功，但缺少 file_token，无法确认远端文件已创建")
    remote_url = str(data.get("url") or data.get("file_url") or "").strip()
    return filename, path, res, {"fileToken": file_token, "remoteUrl": remote_url}
def extract_import_links(values):
    links = []
    for value in values if isinstance(values, list) else [values]:
        if not isinstance(value, str):
            continue
        found = re.findall(r"https?://[^\s<>'\"，。；、]+", value)
        for link in found:
            clean = link.rstrip(".,;:!?)]}，。；：！？）】")
            if clean and clean not in links:
                links.append(clean)
    return links[:10]
def task_progress(stage):
    return {
        "queued": 5,
        "resolving_link": 15,
        "downloading_video": 30,
        "source_ready": 38,
        "transcribing_audio": 52,
        "extracting_visual_text": 68,
        "generating_note": 82,
        "validating_note": 94,
        "success": 100,
        "failed": 100,
        "need_upload": 100,
    }.get(stage or "", 10)
def task_row(row):
    data = dict(row)
    data["taskId"] = data.pop("id")
    data["noteId"] = data.pop("note_id", "") or ""
    data["createdAt"] = data.pop("created_at", "")
    data["errorCode"] = data.pop("error_code", "") or ""
    data["progress"] = task_progress(data.get("stage") or data.get("status"))
    return data
def require_crypto():
    if not serialization or not hashes or not padding or not AESGCM:
        raise RuntimeError("微信支付需要安装 cryptography：pip install cryptography")
def pem_from_env(value_name):
    value = os.getenv(value_name, "").strip()
    if not value:
        return b""
    if "-----BEGIN" not in value and "\n" not in value and "\\n" not in value:
        path = Path(value)
        if path.exists():
            return path.read_bytes()
    return value.replace("\\n", "\n").encode("utf-8")
def rsa_sign(message):
    require_crypto()
    pem = pem_from_env("WECHAT_PAY_PRIVATE_KEY")
    if not pem:
        raise RuntimeError("缺少 WECHAT_PAY_PRIVATE_KEY")
    key = serialization.load_pem_private_key(pem, password=None)
    signature = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")
def verify_wechatpay_message(headers, raw_body, check_timestamp=True):
    require_crypto()
    pem = pem_from_env("WECHAT_PAY_PLATFORM_PUBLIC_KEY")
    if not pem:
        raise RuntimeError("缺少 WECHAT_PAY_PLATFORM_PUBLIC_KEY，不能验证微信支付签名")
    timestamp = str(headers.get("Wechatpay-Timestamp", "")).strip()
    nonce = str(headers.get("Wechatpay-Nonce", "")).strip()
    signature = str(headers.get("Wechatpay-Signature", "")).strip()
    serial = str(headers.get("Wechatpay-Serial", "")).strip()
    if not timestamp or not nonce or not signature or not serial:
        raise RuntimeError("微信支付响应缺少验签头")
    expected_serial = os.getenv("WECHAT_PAY_PLATFORM_SERIAL", "").strip()
    if expected_serial and not hmac.compare_digest(expected_serial, serial):
        raise RuntimeError("微信支付平台公钥ID或证书序列号不匹配")
    try:
        timestamp_number = int(timestamp)
    except ValueError as exc:
        raise RuntimeError("微信支付签名时间戳无效") from exc
    if check_timestamp and abs(int(time.time()) - timestamp_number) > 300:
        raise RuntimeError("微信支付签名时间戳已过期")
    message = f"{timestamp}\n{nonce}\n{raw_body.decode('utf-8')}\n".encode("utf-8")
    public_key = serialization.load_pem_public_key(pem)
    public_key.verify(base64.b64decode(signature), message, padding.PKCS1v15(), hashes.SHA256())
def wechatpay_authorization(method, request_path, body_text=""):
    mchid = os.getenv("WECHAT_PAY_MCH_ID", "").strip()
    serial = os.getenv("WECHAT_PAY_CERT_SERIAL", "").strip()
    if not mchid or not serial:
        raise RuntimeError("缺少 WECHAT_PAY_MCH_ID / WECHAT_PAY_CERT_SERIAL")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    message = f"{method.upper()}\n{request_path}\n{timestamp}\n{nonce}\n{body_text}\n"
    signature = rsa_sign(message)
    return f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{serial}",signature="{signature}"'
def wechatpay_request(method, request_path, payload=None, timeout=30):
    body_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload is not None else ""
    req = Request(
        "https://api.mch.weixin.qq.com" + request_path,
        data=body_text.encode("utf-8") if payload is not None else None,
        method=method.upper(),
    )
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", wechatpay_authorization(method, request_path, body_text))
    try:
        with urlopen(req, timeout=timeout) as response:
            raw_body = response.read()
            verify_wechatpay_message(response.headers, raw_body)
            return json.loads(raw_body.decode("utf-8") or "{}")
    except HTTPError as exc:
        raw_body = exc.read()
        if exc.headers.get("Wechatpay-Signature"):
            verify_wechatpay_message(exc.headers, raw_body)
        try:
            error = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            error = {}
        code = error.get("code") or f"HTTP_{exc.code}"
        message = error.get("message") or "微信支付接口请求失败"
        raise RuntimeError(f"{code}: {message}") from exc
def payment_configuration(channel="mp-weixin"):
    required = [
        "WECHAT_PAY_MCH_ID", "WECHAT_PAY_CERT_SERIAL", "WECHAT_PAY_PRIVATE_KEY",
        "WECHAT_PAY_PLATFORM_PUBLIC_KEY", "WECHAT_PAY_API_V3_KEY", "WECHAT_PAY_NOTIFY_URL",
    ]
    required += ["WECHAT_APP_ID"] if channel == "app" else ["WECHAT_MINI_APP_ID", "WECHAT_MINI_APP_SECRET"]
    missing = [key for key in required if not os.getenv(key, "").strip()]
    invalid = []
    notify_url = os.getenv("WECHAT_PAY_NOTIFY_URL", "").strip()
    if notify_url and not notify_url.startswith("https://") and os.getenv("ALLOW_INSECURE_PAYMENT_NOTIFY", "0") != "1":
        invalid.append("WECHAT_PAY_NOTIFY_URL 必须使用 HTTPS")
    api_key = os.getenv("WECHAT_PAY_API_V3_KEY", "").encode("utf-8")
    if api_key and len(api_key) != 32:
        invalid.append("WECHAT_PAY_API_V3_KEY 必须为 32 字节")
    return {"ready": payment_enabled() and not missing and not invalid, "missing": missing, "invalid": invalid}
def payment_configured(channel="mp-weixin"):
    return payment_configuration(channel)["ready"]
def wechat_openid(code):
    appid = os.getenv("WECHAT_MINI_APP_ID", "").strip()
    secret = os.getenv("WECHAT_MINI_APP_SECRET", "").strip()
    if not appid or not secret or not code:
        raise RuntimeError("小程序支付缺少 AppID、AppSecret 或登录 code")
    url = "https://api.weixin.qq.com/sns/jscode2session?" + urlencode({
        "appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code",
    })
    data = json_request(url, None, method="GET")
    if data.get("errcode") or not data.get("openid"):
        raise RuntimeError(data.get("errmsg") or "微信登录 code 换取 openid 失败")
    return data["openid"]
def create_payment_order(c, user, plan_id, channel, login_code=""):
    if not payment_enabled():
        raise RuntimeError("免费内测期间暂未开放支付")
    plan = PLAN_CONFIG.get(plan_id)
    if not plan:
        raise ValueError("无效会员套餐")
    if channel not in ("mp-weixin", "app"):
        raise ValueError("当前仅支持微信小程序或 App 微信支付")
    if not payment_configured(channel):
        raise RuntimeError("微信支付商户配置未完成，请配置商户号、证书、私钥、回调地址和对应 AppID")
    mchid = os.getenv("WECHAT_PAY_MCH_ID", "").strip()
    appid = os.getenv("WECHAT_APP_ID" if channel == "app" else "WECHAT_MINI_APP_ID", "").strip()
    out_trade_no = time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(5).upper()
    payload = {
        "appid": appid,
        "mchid": mchid,
        "description": "视频知识库-" + plan["name"],
        "out_trade_no": out_trade_no,
        "notify_url": os.getenv("WECHAT_PAY_NOTIFY_URL", "").strip(),
        "amount": {"total": plan["amount"], "currency": "CNY"},
        "attach": plan_id,
    }
    if channel == "mp-weixin":
        payload["payer"] = {"openid": wechat_openid(login_code)}
        request_path = "/v3/pay/transactions/jsapi"
    else:
        request_path = "/v3/pay/transactions/app"
    c.execute(
        """INSERT INTO payment_orders(out_trade_no,user_id,plan,amount,status,channel,prepay_id,transaction_id,created_at,paid_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (out_trade_no, user["id"], plan_id, plan["amount"], "CREATING", channel, "", "", now(), ""),
    )
    c.commit()
    try:
        response = wechatpay_request("POST", request_path, payload)
    except Exception:
        c.execute("UPDATE payment_orders SET status='CREATE_FAILED' WHERE out_trade_no=?", (out_trade_no,))
        c.commit()
        raise
    prepay_id = response.get("prepay_id")
    if not prepay_id:
        c.execute("UPDATE payment_orders SET status='CREATE_FAILED' WHERE out_trade_no=?", (out_trade_no,))
        c.commit()
        raise RuntimeError(response.get("message") or "微信支付下单未返回 prepay_id")
    c.execute(
        "UPDATE payment_orders SET status='NOTPAY',prepay_id=? WHERE out_trade_no=?",
        (prepay_id, out_trade_no),
    )
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    if channel == "mp-weixin":
        package_value = "prepay_id=" + prepay_id
        pay_sign = rsa_sign(f"{appid}\n{timestamp}\n{nonce}\n{package_value}\n")
        client_params = {
            "timeStamp": timestamp, "nonceStr": nonce, "package": package_value,
            "signType": "RSA", "paySign": pay_sign,
        }
    else:
        pay_sign = rsa_sign(f"{appid}\n{timestamp}\n{nonce}\n{prepay_id}\n")
        client_params = {
            "appid": appid, "partnerid": mchid, "prepayid": prepay_id,
            "package": "Sign=WXPay", "noncestr": nonce, "timestamp": int(timestamp), "sign": pay_sign,
        }
    c.commit()
    return {"outTradeNo": out_trade_no, "channel": channel, "clientParams": client_params}
def activate_payment(c, out_trade_no, transaction_id, amount):
    order = c.execute("SELECT * FROM payment_orders WHERE out_trade_no=?", (out_trade_no,)).fetchone()
    if not order:
        raise RuntimeError("支付订单不存在")
    if int(amount) != int(order["amount"]):
        raise RuntimeError("支付金额与订单金额不一致")
    if order["status"] == "SUCCESS":
        return order
    if transaction_id:
        duplicate = c.execute(
            "SELECT 1 FROM payment_orders WHERE transaction_id=? AND out_trade_no<>?",
            (transaction_id, out_trade_no),
        ).fetchone()
        if duplicate:
            raise RuntimeError("微信支付交易号已绑定其他订单")
    plan = PLAN_CONFIG.get(order["plan"])
    if not plan:
        raise RuntimeError("订单套餐无效")
    updated = c.execute(
        "UPDATE payment_orders SET status='SUCCESS',transaction_id=?,paid_at=? WHERE out_trade_no=? AND status!='SUCCESS'",
        (transaction_id or "", now(), out_trade_no),
    )
    if updated.rowcount == 1:
        c.execute(
            "UPDATE users SET member_type=?,remaining_parse_count=remaining_parse_count+? WHERE id=?",
            (plan["member_type"], plan["quota"], order["user_id"]),
        )
    return c.execute("SELECT * FROM payment_orders WHERE out_trade_no=?", (out_trade_no,)).fetchone()
def payment_order_row(order):
    return {
        "outTradeNo": order["out_trade_no"],
        "plan": order["plan"],
        "planName": (PLAN_CONFIG.get(order["plan"]) or {}).get("name", order["plan"]),
        "amount": order["amount"],
        "status": order["status"],
        "channel": order["channel"],
        "createdAt": order["created_at"],
        "paidAt": order["paid_at"],
    }
def query_payment_order(c, user_id, out_trade_no):
    order = c.execute(
        "SELECT * FROM payment_orders WHERE out_trade_no=? AND user_id=?", (out_trade_no, user_id)
    ).fetchone()
    if not order:
        raise ValueError("订单不存在")
    if order["status"] != "SUCCESS" and order["prepay_id"] and payment_configured(order["channel"]):
        mchid = os.getenv("WECHAT_PAY_MCH_ID", "").strip()
        path = f"/v3/pay/transactions/out-trade-no/{quote(out_trade_no)}?mchid={quote(mchid)}"
        result = wechatpay_request("GET", path)
        if result.get("trade_state") == "SUCCESS":
            order = activate_payment(
                c, out_trade_no, result.get("transaction_id", ""),
                (result.get("amount") or {}).get("total", -1),
            )
        elif result.get("trade_state"):
            c.execute("UPDATE payment_orders SET status=? WHERE out_trade_no=?", (result["trade_state"], out_trade_no))
            order = c.execute("SELECT * FROM payment_orders WHERE out_trade_no=?", (out_trade_no,)).fetchone()
    return payment_order_row(order)
def verify_wechatpay_signature(handler, raw_body):
    verify_wechatpay_message(handler.headers, raw_body)
def handle_wechatpay_notify(handler):
    length = int(handler.headers.get("content-length", 0))
    raw_body = handler.rfile.read(length)
    try:
        verify_wechatpay_signature(handler, raw_body)
        envelope = json.loads(raw_body.decode("utf-8"))
        resource = envelope.get("resource") or {}
        if resource.get("algorithm") != "AEAD_AES_256_GCM":
            raise RuntimeError("不支持的微信支付回调加密算法")
        api_key = os.getenv("WECHAT_PAY_API_V3_KEY", "").encode("utf-8")
        if len(api_key) != 32:
            raise RuntimeError("WECHAT_PAY_API_V3_KEY 必须为 32 字节")
        plain = AESGCM(api_key).decrypt(
            resource["nonce"].encode("utf-8"),
            base64.b64decode(resource["ciphertext"]),
            (resource.get("associated_data") or "").encode("utf-8"),
        )
        data = json.loads(plain.decode("utf-8"))
        if data.get("mchid") != os.getenv("WECHAT_PAY_MCH_ID", "").strip():
            raise RuntimeError("支付回调商户号不匹配")
        if data.get("trade_state") == "SUCCESS":
            with conn() as c:
                order = c.execute(
                    "SELECT channel FROM payment_orders WHERE out_trade_no=?", (data["out_trade_no"],)
                ).fetchone()
                if not order:
                    raise RuntimeError("支付订单不存在")
                expected_appid = os.getenv(
                    "WECHAT_APP_ID" if order["channel"] == "app" else "WECHAT_MINI_APP_ID", ""
                ).strip()
                if data.get("appid") != expected_appid:
                    raise RuntimeError("支付回调 AppID 与订单渠道不匹配")
                activate_payment(
                    c, data["out_trade_no"], data.get("transaction_id", ""),
                    (data.get("amount") or {}).get("total", -1),
                )
        return handler.sendj({"code": "SUCCESS", "message": "成功"})
    except Exception as exc:
        return handler.sendj({"code": "FAIL", "message": str(exc)}, 400)
def user_by_token(c, h):
    auth = h.headers.get("authorization", "").replace("Bearer ", "")
    if not auth:
        return None
    return c.execute(
        """SELECT u.* FROM auth_sessions s
           JOIN users u ON u.id=s.user_id
           WHERE s.token=?""",
        (auth,),
    ).fetchone()
def auth_required(h):
    with conn() as c:
        u = user_by_token(c, h)
    return u

def make_note(link, user_id):
    platform = "小红书" if "xiaohongshu" in link or "xhs" in link else "抖音"
    return dict(
        id="note-"+uuid.uuid4().hex[:8], user_id=user_id, title="口碑营销为什么比硬广更容易被信任",
        source_url=link, author="品牌增长研究所", platform=platform, category="市场营销", sub_category="口碑营销",
        tags=["市场营销","信任机制","用户证言"],
        summary="视频围绕“口碑营销为什么有效”展开，强调用户不是被品牌自夸说服，而是被第三方经验、真实使用场景和可验证结果降低顾虑。",
        theory="口碑营销的底层逻辑是信任转移：消费者更容易相信相似用户的真实体验，而不是品牌单方面宣传。",
        steps=["定位目标人群最关心的决策顾虑。","收集真实用户反馈，保留具体场景和结果。","整理为“问题-过程-结果-推荐理由”的结构。","发布时避免空泛夸张，用用户原话增强可信度。"],
        terms=[{"name":"口碑营销","desc":"借助用户评价、推荐和使用经验，让潜在用户形成信任。"},{"name":"信任转移","desc":"用户把对真实使用者的信任转移到品牌或产品上。"}],
        cases={"good":"用真实用户的使用场景、前后变化和具体结果表达。","bad":"只写超好用、闭眼入，没有证据，容易被识别为硬广。"},
        extension={"example":"护肤品牌用28天肤感变化案例解释价值。","confusion":"口碑营销不等于刷好评，前者强调真实经验和长期信任。","qa":["没有大量评价时，先做小样本深访。","负面评价可用于产品改进和风险说明。"]},
        annotations={"highlight":"最有价值的是信任转移这个概念。","question":"不同品类中，用户证言和专家背书的说服力是否不同？","transfer":"可迁移到课程推广、作品集、护肤科普、家居案例。","memory":"别只说好，讲清谁用了、怎么用、解决了什么。"},
        quote="真正有效的口碑，是让用户看到像我这样的人也解决了这个问题。", archived=0, created_at=now(), updated_at=now()
    )
def ensure_terms(value):
    if isinstance(value, str) and value.strip():
        return [{"name": "关键概念", "desc": value.strip()[:800]}]
    if not isinstance(value, list): return []
    out = []
    for item in value[:8]:
        if isinstance(item, dict): out.append({"name": item.get("name") or item.get("concept") or item.get("term") or "概念", "desc": item.get("desc") or item.get("description") or item.get("explanation") or item.get("meaning") or ""})
        else: out.append({"name": str(item)[:16], "desc": str(item)[:80]})
    return out
def ensure_list(value):
    if isinstance(value, list): return [str(x) for x in value if str(x).strip()][:8]
    if isinstance(value, str) and value.strip(): return [value.strip()]
    return []
def analysis_markdown(note):
    core_points = [str(x).strip() for x in note.get("core_points", []) if str(x).strip()][:20]
    action_steps = [str(x).strip() for x in note.get("action_steps", []) if str(x).strip()][:20]
    highlights = [str(x).strip() for x in note.get("highlights", []) if str(x).strip()][:20]
    extra = note.get("extra_info") if isinstance(note.get("extra_info"), dict) else {}
    lines = []
    if core_points:
        lines.append("## 核心信息")
        lines.extend(f"{index}. {item}" for index, item in enumerate(core_points, 1))
    if action_steps:
        lines.append("\n## 可落地操作步骤")
        lines.extend(f"{index}. {item}" for index, item in enumerate(action_steps, 1))
    if highlights:
        lines.append("\n## 高价值原文")
        lines.extend(f"- {item}" for item in highlights)
    extra_labels = [
        ("product_info", "产品信息"),
        ("event_timeline", "事件时间线"),
        ("story_intro", "剧情或故事简述"),
    ]
    extra_items = [(label, str(extra.get(key) or "").strip()) for key, label in extra_labels if str(extra.get(key) or "").strip()]
    if extra_items:
        lines.append("\n## 分类补充信息")
        for label, value in extra_items:
            lines.extend([f"### {label}", value])
    return "\n".join(lines).strip()
def make_note_from_pipeline(link, user_id, payload):
    src = payload.get("source", {})
    n = payload.get("note", {})
    core = n.get("coreKnowledge") if isinstance(n.get("coreKnowledge"), dict) else {}
    ext = n.get("expandInfo") if isinstance(n.get("expandInfo"), dict) else n.get("extension") if isinstance(n.get("extension"), dict) else {}
    cases = n.get("cases") if isinstance(n.get("cases"), dict) else {}
    case_items = ensure_list(core.get("casePositiveNegative"))
    raw_text = payload.get("merged_text", "")
    new_schema = n.get("video_type") and isinstance(n.get("core_points"), list)
    core_points = ensure_list(n.get("core_points"))
    action_steps = ensure_list(n.get("action_steps"))
    highlights = ensure_list(n.get("highlights"))
    extra_info = n.get("extra_info") if isinstance(n.get("extra_info"), dict) else {}
    structured_note = analysis_markdown(n) if new_schema else n.get("structuredNoteMarkdown") or n.get("structured_note_markdown") or core.get("theoryLogic") or n.get("theory") or raw_text[:600]
    return dict(
        id="note-"+uuid.uuid4().hex[:8], user_id=user_id,
        title=(n.get("title") or src.get("title") or "未命名视频笔记")[:80],
        source_url=src.get("source_url") or link,
        author=n.get("author") or src.get("author") or "未识别账号",
        platform=n.get("platform") or src.get("platform") or ("小红书" if "xiaohongshu" in link or "xhs" in link else "抖音"),
        category=n.get("video_type") or n.get("category") or "待分类",
        sub_category=n.get("video_type") or n.get("sub_category") or n.get("subcategory") or "待细分",
        tags=([n.get("video_type"), "AI解析"] if new_schema else ensure_list(n.get("tags")) or ["AI解析"]),
        summary=((core_points[0] if core_points else "") if new_schema else n.get("oneSentenceSummary") or n.get("summary") or raw_text[:160] or "已导入，等待真实解析完成后完善笔记。")[:500],
        theory=(structured_note or "暂无核心知识点，当前视频没有提取到有效信息。")[:12000],
        steps=action_steps if new_schema else ensure_list(core.get("practiceSteps")) or ensure_list(n.get("steps")) or ensure_list(raw_text[:120]),
        terms=ensure_terms(core.get("conceptExplain")) or ensure_terms(n.get("terms")),
        cases={"good": "\n".join(case_items) or cases.get("good", ""), "bad": cases.get("bad", "")},
        extension=({"example": extra_info.get("product_info", ""), "confusion": extra_info.get("event_timeline", ""), "qa": [extra_info.get("story_intro")] if extra_info.get("story_intro") else []} if new_schema else {"example": "", "confusion": "", "qa": []}),
        annotations={"highlight": "", "question": "", "transfer": "", "memory": "", "extra": []},
        quote=(highlights[0] if highlights else "") if new_schema else n.get("quote") or raw_text[:80],
        archived=0, created_at=now(), updated_at=now()
    )
def insert_note(c, n):
    c.execute("""INSERT INTO notes VALUES (:id,:user_id,:title,:source_url,:author,:platform,:category,:sub_category,:tags,:summary,:theory,:steps,:terms,:cases,:extension,:annotations,:quote,:archived,:created_at,:updated_at)""",
        {**n, **{k:json.dumps(n[k],ensure_ascii=False) for k in ["tags","steps","terms","cases","extension","annotations"]}})
def parser_status():
    return {
        "tikhubConfigured": bool(os.getenv("TIKHUB_API_KEY", "").strip()),
        "thirdPartyConfigured": bool(os.getenv("THIRD_PARTY_PARSE_URL", "").strip()),
        "llmConfigured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "whisperAvailable": bool(importlib.util.find_spec("faster_whisper") or os.getenv("WHISPER_CLI", "").strip()),
        "paddleOcrAvailable": bool(importlib.util.find_spec("paddleocr")),
        "rapidOcrAvailable": bool(importlib.util.find_spec("rapidocr_onnxruntime")),
        "ytDlpAvailable": bool(importlib.util.find_spec("yt_dlp")),
        "visualOcrEnabled": os.getenv("VISUAL_OCR_ENABLED", "1") == "1",
        "deyoAvailable": bool(find_deyo_cli()),
        "deyoConfigured": bool(os.getenv("DEYO_API_KEY", "").strip()),
        "deyoEnabled": os.getenv("DEYO_ENABLED", "1") == "1",
        "crvAvailable": bool(importlib.util.find_spec("claude_real_video")),
        "crvEnabled": os.getenv("CRV_ENABLED", "1") == "1",
        "ffmpegAvailable": bool(find_ffmpeg()),
        "mode": "Deyo链接转写优先" if os.getenv("DEYO_ENABLED", "1") == "1" and find_deyo_cli() else ("CRV真视频优先" if os.getenv("REAL_VIDEO_FIRST", "1") == "1" and os.getenv("CRV_ENABLED", "1") == "1" else ("真实解析优先" if os.getenv("TIKHUB_API_KEY", "").strip() or os.getenv("THIRD_PARTY_PARSE_URL", "").strip() else "公开Meta兜底")),
    }
def update_task(task_id, status, stage=None, message=None, error_code=None, note_id=None):
    with conn() as c:
        c.execute(
            "UPDATE tasks SET status=?,stage=?,message=?,error_code=?,note_id=COALESCE(?,note_id) WHERE id=?",
            (status, stage or status, message or "", error_code, note_id, task_id),
        )

def process_import_task(task_id, user_id, link):
    try:
        update_task(task_id, "processing", "resolving_link", "正在解析视频链接")
        key=link_key(link)
        cached=None
        payload=None
        with conn() as c:
            cached=c.execute("SELECT payload FROM parse_cache WHERE cache_key=?",(key,)).fetchone()
            if cached:
                try:
                    payload=json.loads(cached["payload"])
                    validate_payload(payload, link)
                except PipelineError:
                    c.execute("DELETE FROM parse_cache WHERE cache_key=?",(key,))
                    cached=None
                    payload=None
        if payload is None:
            payload=run_pipeline(
                link,
                progress=lambda stage, message: update_task(task_id, "processing", stage, message),
            )
        else:
            update_task(task_id, "processing", "validating_note", "缓存命中，正在校验并恢复结构化笔记")
        n=make_note_from_pipeline(link,user_id,payload)
        assert_note_quality(n)
        with conn() as c:
            if not cached:
                c.execute("INSERT OR REPLACE INTO parse_cache VALUES(?,?,?,?)",(key,link,json.dumps(payload,ensure_ascii=False),now()))
            insert_note(c,n)
            c.execute("UPDATE tasks SET status=?,note_id=?,stage=?,message=?,error_code=? WHERE id=?",("success",n["id"],"success","解析完成，已生成结构化笔记" + ("（缓存命中）" if cached else ""),"",task_id))
            c.execute("UPDATE users SET remaining_parse_count=remaining_parse_count-1, today_parse_count=today_parse_count+1 WHERE id=?",(user_id,))
    except PipelineError as e:
        task_status = "failed" if e.status == "need_upload" else e.status
        update_task(task_id, task_status, task_status, e.message, e.code)
    except Exception as e:
        update_task(task_id, "failed", "failed", str(e), "PIPELINE_FAILED")

def recover_pending_tasks():
    with conn() as c:
        rows=c.execute(
            "SELECT id,user_id,link FROM tasks WHERE status IN ('queued','processing') ORDER BY created_at"
        ).fetchall()
        for row in rows:
            c.execute(
                "UPDATE tasks SET status='queued',stage='queued',message='服务已恢复，任务重新进入后台队列',error_code='' WHERE id=?",
                (row["id"],),
            )
    for row in rows:
        threading.Thread(
            target=process_import_task,
            args=(row["id"],row["user_id"],row["link"]),
            daemon=True,
        ).start()
    return len(rows)

def keep_active_tasks_awake():
    """Keep Render's free web instance awake only while background work exists."""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not render_url:
        return
    while True:
        time.sleep(60)
        try:
            with conn() as c:
                active = c.execute(
                    "SELECT 1 FROM tasks WHERE status IN ('queued','processing') LIMIT 1"
                ).fetchone()
            if active:
                with urlopen(render_url + "/api/ready", timeout=15) as response:
                    response.read(32)
        except Exception as exc:
            print(f"Active-task keepalive failed: {exc}")

def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        old = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'").fetchone()
        if old:
            cols = [r["name"] for r in c.execute("PRAGMA table_info(notes)").fetchall()]
            if "user_id" not in cols:
                for table in ["notes", "users", "folders", "tags", "tasks"]:
                    c.execute(f"DROP TABLE IF EXISTS {table}")
        c.execute("""CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,phone TEXT UNIQUE,password TEXT,token TEXT,member_type TEXT,today_parse_count INT,remaining_parse_count INT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS auth_sessions(token TEXT PRIMARY KEY,user_id TEXT,created_at TEXT,last_seen_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY,user_id TEXT,title TEXT,source_url TEXT,author TEXT,platform TEXT,category TEXT,sub_category TEXT,tags TEXT,summary TEXT,theory TEXT,steps TEXT,terms TEXT,cases TEXT,extension TEXT,annotations TEXT,quote TEXT,archived INT DEFAULT 0,created_at TEXT,updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,count INT DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tags(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,count INT DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_id TEXT,status TEXT,note_id TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS parse_cache(cache_key TEXT PRIMARY KEY,source_url TEXT,payload TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS export_records(id TEXT PRIMARY KEY,user_id TEXT,kind TEXT,filename TEXT,path TEXT,note_count INT,created_at TEXT,remote_url TEXT,meta TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS integrations(user_id TEXT,provider TEXT,access_token TEXT,refresh_token TEXT,expires_at INT,meta TEXT,updated_at TEXT,PRIMARY KEY(user_id,provider))""")
        c.execute("""CREATE TABLE IF NOT EXISTS oauth_states(state TEXT PRIMARY KEY,user_id TEXT,provider TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS payment_orders(
            out_trade_no TEXT PRIMARY KEY,user_id TEXT,plan TEXT,amount INT,status TEXT,channel TEXT,
            prepay_id TEXT,transaction_id TEXT,created_at TEXT,paid_at TEXT
        )""")
        task_cols = [r["name"] for r in c.execute("PRAGMA table_info(tasks)").fetchall()]
        for name in ["link", "stage", "error_code", "message"]:
            if name not in task_cols:
                c.execute(f"ALTER TABLE tasks ADD COLUMN {name} TEXT")
        export_cols = [r["name"] for r in c.execute("PRAGMA table_info(export_records)").fetchall()]
        for name in ["remote_url", "meta"]:
            if name not in export_cols:
                c.execute(f"ALTER TABLE export_records ADD COLUMN {name} TEXT")
        c.execute("DELETE FROM integrations WHERE provider=?", ("wps",))
        c.execute("UPDATE export_records SET kind='word' WHERE kind IN ('wps','wps-local')")
        c.execute("DELETE FROM oauth_states WHERE created_at < datetime('now','-30 minutes','localtime')")
        c.execute("DELETE FROM auth_sessions WHERE created_at < datetime('now','-90 days','localtime')")
        c.execute(
            """INSERT OR IGNORE INTO auth_sessions(token,user_id,created_at,last_seen_at)
               SELECT token,id,?,? FROM users WHERE COALESCE(token,'')<>''""",
            (now(), now()),
        )
        if not c.execute("SELECT 1 FROM users WHERE phone='13800138000'").fetchone():
            uid="user-demo"; tk=token()
            c.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",(uid,"13800138000",hash_password("Aa123456"),tk,"演示账号" if public_demo_mode() else "VIP用户",0,0 if public_demo_mode() else 300))
            for name in ["全部笔记","测试文件夹"]: c.execute("INSERT INTO folders VALUES(?,?,?,?)",("folder-"+uuid.uuid4().hex[:6],uid,name,5 if name=="全部笔记" else 0))
            for name in ["学习方法","效率提升","时间管理"]: c.execute("INSERT INTO tags VALUES(?,?,?,?)",("tag-"+uuid.uuid4().hex[:6],uid,name,1))
            for i in range(5): insert_note(c, make_note(f"https://www.douyin.com/video/mock-{i}", uid))

class H(BaseHTTPRequestHandler):
    def end_headers(self):
        configured = [item.strip() for item in os.getenv("CORS_ORIGIN", "*").split(",") if item.strip()]
        request_origin = self.headers.get("Origin", "")
        allow_origin = "*" if "*" in configured else (request_origin if request_origin in configured else (configured[0] if configured else ""))
        if allow_origin:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type,Authorization")
        super().end_headers()
    def sendj(self, data, code=200):
        b=j(data); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def send_static(self, raw_path):
        relative = raw_path.lstrip("/")
        candidate = (H5_DIST_DIR / relative).resolve()
        root = H5_DIST_DIR.resolve()
        if not str(candidate).startswith(str(root)) or not candidate.is_file():
            candidate = root / "index.html"
        if not candidate.is_file():
            return self.sendj({"error":"H5 build not found"},404)
        data = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(data)
    def redirect(self, url):
        self.send_response(302); self.send_header("Location", url); self.end_headers()
    def do_OPTIONS(self): self.sendj({"ok":True})
    def user_or_401(self):
        u=auth_required(self)
        if not u: self.sendj({"error":"unauthorized"},401)
        return u
    def do_POST(self):
        p=api_path(urlparse(self.path).path)
        if p=="/api/payments/wechat/notify":
            return handle_wechatpay_notify(self)
        b=body(self)
        with conn() as c:
            if p=="/api/auth/register":
                phone=str(b.get("phone") or "").strip(); password=str(b.get("password") or "")
                if not re.fullmatch(r"1\d{10}",phone): return self.sendj({"error":"请输入有效的11位手机号"},400)
                if len(password)<6 or len(password)>20 or not re.search(r"[A-Za-z]",password) or not re.search(r"\d",password): return self.sendj({"error":"密码需为6-20位字母和数字组合"},400)
                if c.execute("SELECT 1 FROM users WHERE phone=?",(b.get("phone"),)).fetchone(): return self.sendj({"error":"手机号已被占用"},400)
                c.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)",("user-"+uuid.uuid4().hex[:8],phone,hash_password(password),"", "内测用户",0,free_beta_quota())); return self.sendj({"ok":True},201)
            if p=="/api/auth/login":
                u=c.execute("SELECT * FROM users WHERE phone=?",(b.get("phone"),)).fetchone()
                if not u or not verify_password(b.get("password") or "",u["password"]): return self.sendj({"error":"账号密码不匹配"},400)
                if not str(u["password"] or "").startswith("pbkdf2_sha256$"):
                    c.execute("UPDATE users SET password=? WHERE id=?",(hash_password(b.get("password") or ""),u["id"]))
                tk=token()
                c.execute(
                    "INSERT INTO auth_sessions(token,user_id,created_at,last_seen_at) VALUES(?,?,?,?)",
                    (tk,u["id"],now(),now()),
                )
                return self.sendj({"token":tk,"phone":u["phone"],"memberType":u["member_type"],"todayParseCount":u["today_parse_count"],"remainingParseCount":u["remaining_parse_count"]})
            u=self.user_or_401(); 
            if not u: return
            if p=="/api/import-tasks":
                links=extract_import_links(b.get("links") or [])
                if not links: return self.sendj({"error":"未识别到有效视频链接"},400)
                if public_demo_mode():
                    used=c.execute("SELECT COUNT(*) n FROM tasks WHERE created_at>=datetime('now','localtime','start of day')").fetchone()["n"]
                    if used>=public_demo_daily_limit(): return self.sendj({"error":"今日公开演示额度已用完，请改天再试"},429)
                    if len(links)>1: return self.sendj({"error":"简历演示版每次只能解析1条链接"},400)
                if u["remaining_parse_count"] < len(links): return self.sendj({"error":"额度不足"},400)
                first_task=None; created=[]
                for link in links:
                    tid="task-"+uuid.uuid4().hex[:8]
                    c.execute("INSERT INTO tasks(id,user_id,status,note_id,created_at,link,stage,message) VALUES(?,?,?,?,?,?,?,?)",(tid,u["id"],"queued","",now(),link,"queued","任务已入队"))
                    first_task=first_task or tid
                    created.append({"taskId":tid,"status":"queued","stage":"queued","progress":5,"link":link})
                # Make every task durable before a background worker starts. The worker is
                # independent of the browser page and can therefore continue after navigation.
                c.commit()
                for task in created:
                    threading.Thread(
                        target=process_import_task,
                        args=(task["taskId"],u["id"],task["link"]),
                        daemon=True,
                    ).start()
                return self.sendj({"taskId":first_task,"noteId":None,"count":len(links),"successCount":0,"created":created},201)
            m=re.fullmatch(r"/api/notes/([^/]+)/annotations",p)
            if m:
                r=c.execute("SELECT annotations FROM notes WHERE id=? AND user_id=?",(m.group(1),u["id"])).fetchone()
                if not r: return self.sendj({"error":"笔记不存在"},404)
                a=json.loads(r["annotations"]); a.setdefault("extra",[]).append(b.get("text","")); c.execute("UPDATE notes SET annotations=?,updated_at=? WHERE id=?",(json.dumps(a,ensure_ascii=False),now(),m.group(1))); return self.sendj({"ok":True})
            m=re.fullmatch(r"/api/notes/([^/]+)/archive",p)
            if m: c.execute("UPDATE notes SET archived=1 WHERE id=? AND user_id=?",(m.group(1),u["id"])); return self.sendj({"ok":True})
            if p in ["/api/sync/feishu","/api/export/word","/api/export/markdown"]:
                try:
                    ids = b.get("ids") or ([b.get("id")] if b.get("id") else [])
                    notes = load_export_notes(c, u["id"], ids)
                    if not notes: return self.sendj({"error":"没有可导出的笔记"},400)
                    if p == "/api/sync/feishu":
                        filename, path, remote, remote_details = sync_to_feishu(c, u["id"], notes)
                        kind = "feishu"
                        remote_url = remote_details["remoteUrl"]
                        remote_meta = json.dumps({"fileToken": remote_details["fileToken"]}, ensure_ascii=False)
                    elif p == "/api/export/word":
                        filename, path = write_docx_export(notes, "video-knowledge-word")
                        kind = "word"
                        remote_url = ""
                        remote_meta = ""
                    else:
                        prefix = "markdown-export"
                        filename, path = write_markdown_export(notes, prefix)
                        kind = "markdown"
                        remote_url = ""
                        remote_meta = ""
                    c.execute(
                        """INSERT INTO export_records(id,user_id,kind,filename,path,note_count,created_at,remote_url,meta)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        ("export-"+uuid.uuid4().hex[:8],u["id"],kind,filename,str(path),len(notes),now(),remote_url,remote_meta),
                    )
                    result = {"ok":True,"kind":kind,"count":len(notes),"filename":filename,"downloadUrl":f"{public_api_base()}/exports/{filename}","remoteUrl":remote_url,"time":now()}
                    if kind == "feishu":
                        result["fileToken"] = remote_details["fileToken"]
                    return self.sendj(result)
                except Exception as exc:
                    return self.sendj({"error":str(exc)},400)
            if p=="/api/payments/orders":
                try:
                    result=create_payment_order(c,u,b.get("plan"),b.get("channel") or "mp-weixin",b.get("loginCode") or "")
                    return self.sendj(result,201)
                except (ValueError,RuntimeError) as exc:
                    return self.sendj({"error":str(exc)},400)
            if p=="/api/vip/buy":
                return self.sendj({"error":"旧版模拟购买接口已停用，请使用微信支付订单接口"},410)
            if p=="/api/folders": c.execute("INSERT INTO folders VALUES(?,?,?,0)",("folder-"+uuid.uuid4().hex[:6],u["id"],b.get("name","新文件夹"))); return self.sendj({"ok":True},201)
            if p=="/api/tags": c.execute("INSERT INTO tags VALUES(?,?,?,0)",("tag-"+uuid.uuid4().hex[:6],u["id"],b.get("name","新标签"))); return self.sendj({"ok":True},201)
        self.sendj({"error":"not found"},404)
    def do_GET(self):
        raw_path=urlparse(self.path).path
        p=api_path(raw_path); q=parse_qs(urlparse(self.path).query)
        if SERVE_H5 and not (p.startswith("/api/") or p.startswith("/exports/")):
            return self.send_static(raw_path)
        if p=="/api/health": return self.sendj({"ok":True,"time":now()})
        if p=="/api/ready":
            try:
                with conn() as ready_connection:
                    ready_connection.execute("SELECT 1").fetchone()
                return self.sendj({"ok":True,"time":now()})
            except Exception as exc:
                return self.sendj({"ok":False,"error":str(exc)},503)
        m_oauth=re.fullmatch(r"/api/oauth/(feishu)/callback",p)
        if m_oauth:
            provider=m_oauth.group(1); code=(q.get("code") or [""])[0]; state=(q.get("state") or [""])[0]
            try:
                if not code or not state: raise RuntimeError("缺少授权 code/state")
                with conn() as c:
                    row=c.execute("SELECT * FROM oauth_states WHERE state=? AND provider=?", (state, provider)).fetchone()
                    if not row: raise RuntimeError("授权状态已过期，请重新发起授权")
                    token_data = exchange_feishu_code(code)
                    upsert_integration(c, row["user_id"], provider, token_data)
                    c.execute("DELETE FROM oauth_states WHERE state=?", (state,))
                return self.redirect(frontend_done_url(provider, True))
            except Exception:
                return self.redirect(frontend_done_url(provider, False))
        m_export=re.fullmatch(r"/exports/([^/]+)",p)
        if m_export:
            path=(EXPORT_DIR / m_export.group(1)).resolve()
            if not str(path).startswith(str(EXPORT_DIR.resolve())) or not path.exists():
                return self.sendj({"error":"not found"},404)
            data=path.read_bytes()
            ctype="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if path.suffix.lower()==".docx" else "text/markdown; charset=utf-8"
            self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(data))); self.send_header("Content-Disposition",f'attachment; filename="{path.name}"'); self.end_headers(); self.wfile.write(data); return
        u=self.user_or_401()
        if not u: return
        with conn() as c:
            if p=="/api/me": return self.sendj({"phone":u["phone"],"memberType":u["member_type"],"todayParseCount":u["today_parse_count"],"remainingParseCount":u["remaining_parse_count"]})
            if p=="/api/integrations/status":
                rows={r["provider"]:dict(r) for r in c.execute("SELECT * FROM integrations WHERE user_id=?", (u["id"],))}
                feishu_row = rows.get("feishu") or {}
                feishu_token_valid = bool(
                    feishu_row.get("access_token")
                    and (
                        not feishu_row.get("expires_at")
                        or feishu_row["expires_at"] > int(time.time()) + 60
                        or feishu_row.get("refresh_token")
                    )
                )
                return self.sendj({
                    "feishu":{"configured":bool(os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET")),"authorized":feishu_token_valid,"ready":bool(os.getenv("FEISHU_APP_ID") and os.getenv("FEISHU_APP_SECRET") and os.getenv("FEISHU_PARENT_NODE") and feishu_token_valid),"expiresAt":feishu_row.get("expires_at")},
                    "localExport":{"formats":["docx","markdown"]},
                    "hints":{"feishuParentNode":bool(os.getenv("FEISHU_PARENT_NODE"))}
                })
            m_auth=re.fullmatch(r"/api/integrations/(feishu)/auth-url",p)
            if m_auth:
                state=uuid.uuid4().hex
                provider=m_auth.group(1)
                c.execute("INSERT OR REPLACE INTO oauth_states VALUES(?,?,?,?)", (state, u["id"], provider, now()))
                try:
                    url = feishu_auth_url(state)
                except ValueError as exc:
                    return self.sendj({"error":str(exc)},400)
                return self.sendj({"url":url,"redirectUri":oauth_redirect_url(provider)})
            if p=="/api/system/parser-status": return self.sendj(parser_status())
            if p=="/api/payments/config":
                mini_config = payment_configuration("mp-weixin")
                app_config = payment_configuration("app")
                return self.sendj({
                    "enabled":payment_enabled(),
                    "freeBeta":not payment_enabled(),
                    "freeBetaQuota":free_beta_quota(),
                    "mpWeixinConfigured":mini_config["ready"],
                    "appConfigured":app_config["ready"],
                    "missing":{"mpWeixin":mini_config["missing"],"app":app_config["missing"]},
                    "invalid":{"mpWeixin":mini_config["invalid"],"app":app_config["invalid"]},
                    "plans":[{"id":key,**value} for key,value in PLAN_CONFIG.items()],
                })
            if p=="/api/dashboard":
                total=c.execute("SELECT COUNT(*) n FROM notes WHERE user_id=? AND archived=0",(u["id"],)).fetchone()["n"]
                folders=c.execute("SELECT COUNT(*) n FROM folders WHERE user_id=?",(u["id"],)).fetchone()["n"]
                tags=c.execute("SELECT COUNT(*) n FROM tags WHERE user_id=?",(u["id"],)).fetchone()["n"]
                week_parsed=c.execute(
                    """SELECT COUNT(*) n FROM notes
                       WHERE user_id=? AND archived=0
                       AND created_at >= datetime(
                         'now','localtime','start of day',
                         '-' || ((CAST(strftime('%w','now','localtime') AS INTEGER)+6)%7) || ' days'
                       )""",
                    (u["id"],)
                ).fetchone()["n"]
                chart=[dict(r) for r in c.execute("SELECT category name,COUNT(*) count FROM notes WHERE user_id=? GROUP BY category",(u["id"],))]
                return self.sendj({"user":{"phone":u["phone"],"memberType":u["member_type"],"todayParseCount":u["today_parse_count"],"remainingParseCount":u["remaining_parse_count"]},"stats":{"totalNotes":total,"todayNew":u["today_parse_count"],"weekParsed":week_parsed,"folderCount":folders,"tagCount":tags},"categoryChart":chart})
            if p=="/api/notes":
                page=int(q.get("page",["1"])[0]); size=int(q.get("pageSize",["20"])[0]); kw=q.get("keyword",[""])[0]; filter_name=q.get("filterName",[""])[0]; sort=q.get("sort",[""])[0]; where="user_id=? AND archived=0"; args=[u["id"]]
                if kw: where+=" AND (title LIKE ? OR summary LIKE ?)"; args += [f"%{kw}%",f"%{kw}%"]
                if filter_name and filter_name!="全部笔记":
                    where+=" AND (category=? OR sub_category=? OR tags LIKE ?)"
                    args += [filter_name, filter_name, f"%{filter_name}%"]
                order = "created_at DESC" if sort=="导入时间" else "updated_at DESC"
                total=c.execute(f"SELECT COUNT(*) n FROM notes WHERE {where}",args).fetchone()["n"]; rows=c.execute(f"SELECT * FROM notes WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",args+[size,(page-1)*size]).fetchall()
                return self.sendj({"items":[note_row(r) for r in rows],"total":total,"hasMore":page*size<total})
            m=re.fullmatch(r"/api/notes/([^/]+)",p)
            if m:
                r=c.execute("SELECT * FROM notes WHERE id=? AND user_id=?",(m.group(1),u["id"])).fetchone(); return self.sendj(note_row(r) if r else {"error":"not found"}, 200 if r else 404)
            if p=="/api/import-tasks":
                page=max(1,int(q.get("page",["1"])[0])); size=min(50,max(1,int(q.get("pageSize",["20"])[0])))
                total=c.execute("SELECT COUNT(*) n FROM tasks WHERE user_id=?",(u["id"],)).fetchone()["n"]
                rows=c.execute(
                    """SELECT t.*,n.title,n.platform FROM tasks t LEFT JOIN notes n ON n.id=t.note_id
                       WHERE t.user_id=? ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                    (u["id"],size,(page-1)*size),
                ).fetchall()
                return self.sendj({"items":[task_row(r) for r in rows],"total":total,"hasMore":page*size<total})
            if p=="/api/payments/orders":
                rows=c.execute(
                    "SELECT * FROM payment_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
                    (u["id"],),
                ).fetchall()
                return self.sendj({"items":[payment_order_row(r) for r in rows]})
            m=re.fullmatch(r"/api/import-tasks/([^/]+)",p)
            if m:
                r=c.execute("SELECT * FROM tasks WHERE id=? AND user_id=?",(m.group(1),u["id"])).fetchone()
                return self.sendj(task_row(r) if r else {"status":"failed","errorCode":"TASK_NOT_FOUND","message":"任务不存在","progress":100},200 if r else 404)
            m=re.fullmatch(r"/api/payments/orders/([A-Za-z0-9_-]+)",p)
            if m:
                try:
                    return self.sendj(query_payment_order(c,u["id"],m.group(1)))
                except (ValueError,RuntimeError) as exc:
                    return self.sendj({"error":str(exc)},400)
            if p=="/api/folders": return self.sendj({"items":[dict(r) for r in c.execute("SELECT * FROM folders WHERE user_id=?",(u["id"],))]})
            if p=="/api/tags": return self.sendj({"items":[dict(r) for r in c.execute("SELECT * FROM tags WHERE user_id=?",(u["id"],))]})
            if p=="/api/export-records":
                items=[]
                for r in c.execute("SELECT * FROM export_records WHERE user_id=? ORDER BY created_at DESC LIMIT 30",(u["id"],)):
                    item=dict(r); item["downloadUrl"]=f"{public_api_base()}/exports/{item['filename']}"
                    try: item["remoteMeta"] = json.loads(item.pop("meta") or "{}")
                    except json.JSONDecodeError: item["remoteMeta"] = {}
                    items.append(item)
                return self.sendj({"items":items})
        self.sendj({"error":"not found"},404)
    def do_PATCH(self):
        p=api_path(urlparse(self.path).path); b=body(self); u=self.user_or_401()
        if not u: return
        with conn() as c:
            m=re.fullmatch(r"/api/notes/([^/]+)",p)
            if m:
                mp={"sub_category":"sub_category"}; allowed={"title","category","sub_category","summary","theory","steps","terms","cases","extension","annotations","quote","tags"}; data={k:v for k,v in b.items() if k in allowed}
                vals={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in data.items()}; vals["updated_at"]=now(); vals["id"]=m.group(1); vals["user_id"]=u["id"]; sets=",".join([f"{k}=:{k}" for k in vals if k not in ["id","user_id"]]); c.execute(f"UPDATE notes SET {sets} WHERE id=:id AND user_id=:user_id",vals); r=c.execute("SELECT * FROM notes WHERE id=?",(m.group(1),)).fetchone(); return self.sendj(note_row(r))
            m=re.fullmatch(r"/api/(folders|tags)/([^/]+)",p)
            if m: c.execute(f"UPDATE {m.group(1)} SET name=? WHERE id=? AND user_id=?",(b.get("name"),m.group(2),u["id"])); return self.sendj({"ok":True})
        self.sendj({"error":"not found"},404)
    def do_DELETE(self):
        p=api_path(urlparse(self.path).path); u=self.user_or_401()
        if not u: return
        with conn() as c:
            m=re.fullmatch(r"/api/integrations/(feishu)",p)
            if m:
                c.execute("DELETE FROM integrations WHERE user_id=? AND provider=?",(u["id"],m.group(1)))
                return self.sendj({"ok":True})
            m=re.fullmatch(r"/api/notes/([^/]+)",p)
            if m: c.execute("DELETE FROM notes WHERE id=? AND user_id=?",(m.group(1),u["id"])); return self.sendj({"ok":True})
            m=re.fullmatch(r"/api/(folders|tags)/([^/]+)",p)
            if m: c.execute(f"DELETE FROM {m.group(1)} WHERE id=? AND user_id=?",(m.group(2),u["id"])); return self.sendj({"ok":True})
        self.sendj({"error":"not found"},404)

if __name__=="__main__":
    load_env()
    init()
    recovered=recover_pending_tasks()
    threading.Thread(target=keep_active_tasks_awake, daemon=True).start()
    print(f"API running http://{HOST}:{PORT}; recovered {recovered} background task(s)")
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
