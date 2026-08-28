"""
腾讯云实时语音识别（WebSocket / asr/v2）签名
================================================
官方文档：https://cloud.tencent.com/document/product/1093/48982

设计：后端只负责「签名」，不下发 SecretKey 到浏览器。
  - build_asr_connect_url() 签出 wss:// 连接串返回给前端；
  - 前端（浏览器）直接连 ASR WebSocket、推裸 PCM、收 JSON 转写结果。
音频流不经过后端，延迟最低也最安全。

⚠️ 签名算法要点（与腾讯云 HTTP API 的 TC3-HMAC-SHA256 完全不同）：
  1. 对除 signature 外的所有参数按【字典序】排序，拼成
     "asr.cloud.tencent.com/asr/v2/<appid>?k1=v1&k2=v2..."（不含 wss:// 协议头）；
  2. 用 SecretKey 做 HmacSHA1，再 base64 编码；
  3. signature 必须 urlencode（safe=''，要编码 + / = 等字符），否则偶发鉴权失败。

音频帧协议：直接发【裸 PCM 二进制】，无帧头；结束发文本 {"type":"end"}。
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import time
import uuid
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv(override=True)

TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
ASR_APP_ID = os.getenv("ASR_APP_ID", "")
ASR_ENGINE_MODEL = os.getenv("ASR_ENGINE_MODEL", "16k_zh")
ASR_VOICE_FORMAT = int(os.getenv("ASR_VOICE_FORMAT", "1"))  # 1 = PCM

ASR_HOST = "asr.cloud.tencent.com"


def _sign(secret_key: str, raw: str) -> str:
    """HmacSHA1(raw, secret_key) -> base64。"""
    mac = hmac.new(secret_key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("utf-8")


def build_asr_connect_url(voice_id: str = None) -> dict:
    """签出腾讯云实时语音识别的 WebSocket 连接串，供前端直接连。

    返回：{ url, voice_id, expired }。前端用 url 建 WebSocket，
    逐片发裸 PCM（16kHz/16bit/单声道），最后发 {"type":"end"}；
    服务端返回 JSON，result.voice_text_str 为转写文本，
    result.slice_type == 2 表示该切片结束（文本已稳定）。
    """
    if not (TENCENT_SECRET_ID and TENCENT_SECRET_KEY and ASR_APP_ID):
        raise RuntimeError("未配置 TENCENT_SECRET_ID / TENCENT_SECRET_KEY / ASR_APP_ID")

    timestamp = int(time.time())
    expired = timestamp + 3600  # 签名有效期 1 小时
    voice_id = voice_id or str(uuid.uuid4())

    params = {
        "secretid": TENCENT_SECRET_ID,
        "engine_model_type": ASR_ENGINE_MODEL,
        "voice_id": voice_id,
        "timestamp": timestamp,
        "expired": expired,
        "nonce": timestamp,
        "voice_format": ASR_VOICE_FORMAT,
        "needvad": 1,
    }

    # 第一步：字典序排序后拼签名原文（不含 wss://）
    path = f"/asr/v2/{ASR_APP_ID}"
    query = "&".join(f"{k}={params[k]}" for k in sorted(params))
    raw = f"{ASR_HOST}{path}?{query}"

    # 第二步 + 第三步：HmacSHA1 -> base64 -> urlencode
    signature = quote(_sign(TENCENT_SECRET_KEY, raw), safe="")

    return {
        "url": f"wss://{ASR_HOST}{path}?{query}&signature={signature}",
        "voice_id": voice_id,
        "expired": expired,
    }


if __name__ == "__main__":
    if not TENCENT_SECRET_ID:
        print("未配置 TENCENT_SECRET_ID，跳过自测")
    else:
        out = build_asr_connect_url("test_voice_001")
        assert out["url"].startswith(f"wss://{ASR_HOST}/asr/v2/")
        assert "signature=" in out["url"]
        print("ASR 连接串生成 OK，长度:", len(out["url"]))
        print("voice_id:", out["voice_id"])
