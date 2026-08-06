import os
import re
import json
import uuid
import time
import random
import hmac
import hashlib
import base64
import secrets
import logging
import requests
import asyncio
from typing import List, Dict, Any, Tuple
from urllib.parse import urlencode

logger = logging.getLogger("AIDrawingVideo")

BASE = "https://editor-api-sg.capcutapi.com"

DEFAULT_DEVICE_TEMPLATE = {
    "aid": "359289",
    "app_name": "CapCut",
    "appvr": "8.7.0",
    "version_name": "8.7.0",
    "version_code": "8.7.0",
    "channel": "capcutpc_google",
    "device_platform": "mac",
    "device_type": "MacBookPro17,1",
    "device_brand": "MacBookPro17,1",
    "os_version": "15.7.4",
    "region": "VN",
    "loc": "VN",
    "lan": "vi-VN",
    "pf": "3",
}

TTS_SIGN_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmTd34Lw4b7IuldSXh/zY
CMla+ITdGG5TeWz6ad+OySd4r+IrY45AoqrYUxhQ2dl+7z+i7r/5vEa8rr39BYfB
8AGMQLmZA8HmgpWBsqrn/V6daUALkKnkLb70Fn32CJigIuGXAYqxUdGuI340aC+0
v5Es3puJsHyzf01/AelE4Cdc6bZhQrASJLBh8R3BQToYClmDVSDUQk28o8sl/guA
Z4n303Vj+6Siv1HayPCdV6kpVVnMBAG4+umUbwGmn132N3fgpzLarFF3XyWmS1zh
D/J07iM/rP8GDO9IskHNHd2phrO0G6KzrcFAnTBHjVv+hCBEfzN/no3FNA9AuC36
mwIDAQAB
-----END PUBLIC KEY-----"""

def compact_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def make_x_ss_stub(body_text):
    return hashlib.md5(body_text.encode("utf-8")).hexdigest()

def _der_len(data, pos):
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    nbytes = first & 0x7F
    return int.from_bytes(data[pos : pos + nbytes], "big"), pos + nbytes

def _der_value(data, pos, tag):
    if data[pos] != tag:
        raise ValueError(f"bad DER tag: expected 0x{tag:02x}, got 0x{data[pos]:02x}")
    length, pos = _der_len(data, pos + 1)
    return data[pos : pos + length], pos + length

def _der_int(data, pos):
    raw, pos = _der_value(data, pos, 0x02)
    return int.from_bytes(raw.lstrip(b"\x00"), "big"), pos

def rsa_public_numbers_from_pem(pem):
    b64 = "".join(line for line in pem.splitlines() if not line.startswith("-----"))
    der = base64.b64decode(b64)
    outer, pos = _der_value(der, 0, 0x30)
    if pos != len(der):
        raise ValueError("trailing data in public key")
    _, pos = _der_value(outer, 0, 0x30)
    bit_string, pos = _der_value(outer, pos, 0x03)
    if pos != len(outer) or not bit_string or bit_string[0] != 0:
        raise ValueError("bad subjectPublicKeyInfo")
    rsa_seq, pos = _der_value(bit_string[1:], 0, 0x30)
    if pos != len(bit_string[1:]):
        raise ValueError("trailing data in RSA public key")
    modulus, pos = _der_int(rsa_seq, 0)
    exponent, pos = _der_int(rsa_seq, pos)
    if pos != len(rsa_seq):
        raise ValueError("trailing integer data in RSA public key")
    return modulus, exponent

def rsa_encrypt_pkcs1v15(message, pem=TTS_SIGN_PUBLIC_KEY_PEM):
    modulus, exponent = rsa_public_numbers_from_pem(pem)
    key_len = (modulus.bit_length() + 7) // 8
    msg = message.encode("utf-8") if isinstance(message, str) else bytes(message)
    if len(msg) > key_len - 11:
        raise ValueError("message too long for RSA PKCS#1 v1.5")
    ps_len = key_len - len(msg) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        chunk = secrets.token_bytes(ps_len - len(ps))
        ps.extend(b for b in chunk if b != 0)
    encoded = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + msg
    encrypted = pow(int.from_bytes(encoded, "big"), exponent, modulus).to_bytes(key_len, "big")
    return base64.b64encode(encrypted).decode("ascii")

def make_tts_payload_sign(ssml, extra_info, device_id, app_id):
    ssml_md5 = hashlib.md5(ssml.encode("utf-8")).hexdigest()
    sign_input = f"appid:{app_id}&did:{device_id}&creditDisable:false&ssml:{ssml_md5}"
    if extra_info is not None:
        sign_input += f"&extraInfo:{extra_info}"
    return rsa_encrypt_pkcs1v15(sign_input)

def make_sign_header(url, appvr, device_time, tdid):
    path = url.split("?", 1)[0]
    sign_str = f"9e2c|{path[-7:]}|3|{appvr}|{device_time}|{tdid}|11ac"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

def make_trace_id():
    seed = uuid.uuid4().hex[:32]
    return f"00-{seed}-{seed[:16]}-01"

def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

def common_query(device, babi_param=None, include_region=True):
    q = {
        "app_name": device["app_name"],
        "device_type": device["device_type"],
        "os_version": device["os_version"],
        "channel": device["channel"],
        "version_name": device["version_name"],
        "device_brand": device["device_brand"],
        "device_id": device["device_id"],
        "iid": device["iid"],
        "version_code": device["version_code"],
        "device_platform": device["device_platform"],
        "aid": device["aid"],
    }
    if include_region:
        q["region"] = device["region"]
    if babi_param is not None:
        q["babi_param"] = compact_json(babi_param)
    return q

def base_headers(device, body_text, appid=False):
    now = str(int(time.time()))
    headers = {
        "content-type": "application/json",
        "appvr": device["appvr"],
        "ch": device["channel"],
        "device-time": now,
        "lan": device["lan"],
        "loc": device["loc"],
        "pf": device["pf"],
        "sign-ver": "1",
        "tdid": device["tdid"],
        "x-ss-stub": make_x_ss_stub(body_text),
        "x-ss-dp": device["aid"],
        "x-khronos": now,
        "x-tt-trace-id": make_trace_id(),
        "user-agent": "Cronet/TTNetVersion:1d7cc3b1 2025-07-16 QuicVersion:52c2b40d 2025-04-03",
        "accept-encoding": "gzip, deflate",
        "store-country-code": device["loc"].lower(),
        "store-country-code-src": "did",
        "is-dispatch-us-ttp": "0",
        "is-app-region-us-ttp": "0",
    }
    if appid:
        headers["app-sdk-version"] = device["appvr"]
        headers["appid"] = device["aid"]
    return headers

class CapCutTTSGenerator:
    def __init__(self):
        self.voices: List[Dict[str, Any]] = []
        self._load_voices()

    def _load_voices(self) -> None:
        """Loads available CapCut voices from json config file."""
        json_path = os.path.join(os.path.dirname(__file__), "capcut_voices.json")
        if not os.path.exists(json_path):
            logger.warning(f"capcut_voices.json not found in {json_path}")
            return
            
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            
            self.voices = [
                {
                    "Name": v["display_name"],
                    "ShortName": v["voice_type"],
                    "Gender": "Unknown",
                    "Locale": v["lang"],
                    "FriendlyName": f"{v['lang']} - {v['display_name']} (CapCut)",
                    "resource_id": v["resource_id"]
                }
                for v in raw_list
            ]
            # Sort by locale, then display name
            self.voices.sort(key=lambda x: (x["Locale"], x["Name"]))
        except Exception as e:
            logger.error(f"Failed to load CapCut voices: {e}")

    def get_all_voices(self) -> List[Dict[str, Any]]:
        return self.voices

    def _generate_device(self) -> Dict[str, str]:
        """Generates a randomized device profile to bypass 'shark block only' firewall checks."""
        dev_id = str(random.randint(10**18, 10**19 - 1))
        iid = str(random.randint(10**18, 10**19 - 1))
        tdid = str(random.randint(10**18, 10**19 - 1))
        
        device = DEFAULT_DEVICE_TEMPLATE.copy()
        device.update({
            "device_id": dev_id,
            "iid": iid,
            "tdid": tdid,
        })
        return device

    async def generate_voice(
        self,
        text: str,
        voice: str,  # short name / voice_type
        output_path: str,
        rate: int = 0,
        pitch: int = 0,
        volume: int = 0
    ) -> float:
        """
        Synthesizes speech using CapCut Common Task API.
        Downloads output MP3 to output_path.
        Returns the duration of the audio.
        """
        max_retries = 10
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating CapCut TTS (Lần thử {attempt + 1}/10)...")
                device = self._generate_device()
                
                # 1. Look up resource_id
                resource_id = "7102355709945188865" # Default fallback
                for v in self.voices:
                    if v["ShortName"] == voice:
                        resource_id = v["resource_id"]
                        break
                        
                # Map rate slider (-50 to +50) to CapCut XML rate multiplier
                rate_multiplier = 1.0 + (rate / 100.0)
                rate_str = f"{rate_multiplier:.2f}"
                
                # 2. Build task payload body
                babi = {
                    "feature_entrance": "editor",
                    "feature_entrance_detail": "editor-feature-text_to_speech",
                    "feature_key": "text_to_speech",
                    "scenario": "video_editor",
                }
                
                ssml = (
                    '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">\n'
                    f'    <voice name="{voice}" mock_tone_info="" platform="sami" '
                    f'resource_id="{resource_id}" emotion="" emotion_scale="0" style="" role="" '
                    f'moyin_emotion="" is_clone_tone="false" need_subtitle_timestamp="false">\n'
                    f'        <prosody rate="{rate_str}">{escape_xml(text)}</prosody>\n'
                    f'    </voice>\n'
                    '</speak>'
                )
                
                extra_info = compact_json({"benefit_info": {}})
                payload = {
                    "audio_format": "mp3",
                    "babi_param": compact_json(babi),
                    "credit_disable": False,
                    "extra_info": extra_info,
                    "need_merge_voice": False,
                    "need_subtitle_timestamp": False,
                    "scene": "text_to_speech",
                    "ssml": ssml,
                }
                payload["sign"] = make_tts_payload_sign(ssml, extra_info, device["device_id"], device["aid"])
                
                body = {
                    "bind_id": str(uuid.uuid4()),
                    "can_queue": True,
                    "enter_from": "text_to_speech",
                    "tasks": [
                        {
                            "context": str(uuid.uuid4()),
                            "payload": compact_json(payload),
                            "req_key": "sami_text_to_speech",
                            "task_version": "v3",
                        }
                    ],
                }
                
                body_text = compact_json(body)
                path = "/lv/v1/common_task/new"
                query = common_query(device, babi, include_region=True)
                url = BASE + path + "?" + urlencode(query)
                
                headers = base_headers(device, body_text, appid=True)
                headers["sign"] = make_sign_header(url, device["appvr"], headers["device-time"], device["tdid"])
                
                logger.info(f"Submitting CapCut TTS request for voice '{voice}'...")
                loop = asyncio.get_event_loop()
                
                # Async HTTP Call using executor to prevent blocking event loop
                resp = await loop.run_in_executor(
                    None,
                    lambda: requests.post(url, headers=headers, data=body_text.encode("utf-8"), timeout=60)
                )
                
                if resp.status_code != 200:
                    raise RuntimeError(f"CapCut TTS request failed with HTTP {resp.status_code}: {resp.text}")
                    
                data = resp.json()
                if data.get("ret") != "0":
                    raise RuntimeError(f"CapCut TTS error: {data.get('errmsg')}")
                    
                task = data["data"]["tasks"][0]
                task_id = task["id"]
                token = task["token"]
                
                # 3. Poll task query status
                logger.info(f"Polling CapCut TTS task {task_id}...")
                req_key = "sami_text_to_speech"
                audio_url = ""
                duration_ms = 0
                
                for i in range(30):
                    await asyncio.sleep(2)
                    
                    qbody = {
                        "tasks": [
                            {
                                "bind_id": "",
                                "id": task_id,
                                "req_key": req_key,
                                "task_version": "v3",
                                "token": token
                            }
                        ]
                    }
                    qbody_text = compact_json(qbody)
                    qpath = "/lv/v1/common_task/query"
                    qquery = common_query(device, None, include_region=False)
                    qurl = BASE + qpath + "?" + urlencode(qquery)
                    
                    qheaders = base_headers(device, qbody_text, appid=True)
                    qheaders["sign"] = make_sign_header(qurl, device["appvr"], qheaders["device-time"], device["tdid"])
                    
                    qresp = await loop.run_in_executor(
                        None,
                        lambda: requests.post(qurl, headers=qheaders, data=qbody_text.encode("utf-8"), timeout=60)
                    )
                    
                    if qresp.status_code != 200:
                        continue
                        
                    qdata = qresp.json()
                    qtask = qdata["data"]["tasks"][0]
                    status = qtask["status"]
                    
                    if status == "succeed":
                        payload_data = json.loads(qtask["payload"])
                        sub = payload_data["audio_subtitles"][0]
                        audio_url = sub["speech_url"]
                        duration_ms = sub.get("duration", 0)
                        break
                    elif status == "failed":
                        raise RuntimeError(f"CapCut task execution failed: {qtask.get('detail_info')}")
                        
                if not audio_url:
                    raise TimeoutError("CapCut TTS polling timed out.")
                    
                logger.info(f"CapCut TTS completed. Downloading speech audio...")
                
                # 4. Download file
                audio_resp = await loop.run_in_executor(
                    None,
                    lambda: requests.get(audio_url, timeout=60)
                )
                
                if audio_resp.status_code != 200:
                    raise RuntimeError(f"Failed to download audio from {audio_url}")
                    
                with open(output_path, "wb") as f:
                    f.write(audio_resp.content)
                    
                duration = duration_ms / 1000.0 if duration_ms > 0 else 1.0
                logger.info(f"Downloaded CapCut audio file successfully. Duration: {duration:.2f}s")
                return duration
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Thất bại tạo CapCut TTS sau {max_retries} lần thử.")
                    raise e
                
                delay = random.uniform(2.0, 5.0)
                logger.warning(f"Lỗi tạo CapCut TTS ở lần thử {attempt + 1}: {e}. Đang thử lại sau {delay:.2f}s...")
                await asyncio.sleep(delay)
