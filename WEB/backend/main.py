import os
import sys
import time
import uuid
import json
import logging
import asyncio
import hashlib
import threading
import requests
import jwt
import platform
import subprocess
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image
import io
import base64
import boto3

# Import configurations
from config import (
    DISCORD_WEBHOOK_URL, UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, ASSETS_DIR, BASE_DIR,
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
)

# Add packages to path
sys.path.append(BASE_DIR)

# Import engine logic
from engine.pipeline import PipelineEngine
from tts.generator import EdgeTTSGenerator
from tts.capcut_generator import CapCutTTSGenerator
from utils.logger import register_log_callback, get_next_log, setup_logger

# Setup licensing credentials & functions locally
def get_hwid() -> str:
    try:
        if platform.system() == "Windows":
            creation_flags = subprocess.CREATE_NO_WINDOW
            return subprocess.check_output('wmic csproduct get uuid', creationflags=creation_flags).decode().split('\n')[1].strip()
        import uuid as _uuid
        return str(_uuid.getnode())
    except Exception:
        import uuid as _uuid
        return str(_uuid.getnode())

def generate_signature(key: str, hwid: str, timestamp: str) -> str:
    raw_str = f"{key}{hwid}{timestamp}{CLIENT_SECRET_SALT}"
    return hashlib.sha256(raw_str.encode()).hexdigest()

# Setup root logger
logger = setup_logger()

app = FastAPI(title="DKC Video Drawing Web API", version="26.7.30")

# Enable CORS for Vercel Frontend and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/static/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# License verification credentials (copied from auth.py)
WORKER_URL = "https://jolly-wave-59b9.cuongvunhat755.workers.dev/"
CLIENT_SECRET_SALT = "DkcTool_S3cr3t_S4lt_2026!@#"
RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyFKks96pTE/5vhmrzttq
XL8867VLWTI+MzVWDqrtD/DWYoYNJ52dvz0nzjbDPdgKeB8BrKrMUCbOZYXkmonO
4a4k3c0/rUe0kADGSbMj8bOjgs5A9YFOcwfeuDBQICJN2rWf7umeVZ6UkhBAl3oZ
toKtYi9RVbr9CL36j6uDTejKY9Q+F0IDOuuSuJ0jdXk0G6txNxmYi6+FmMCHvN6n
lY0BBazG4/JzPkfgEAlD+9LJAbvEynSG48SZ6YCDC2W1ygGd3WFm3xkPXTvSnltq
BRqcm1PZqtSxCrmRycF1GEKbAJqn/N3+mW5ou7m506PGBvfza337qV0osfETDC2v
GwIDAQAB
-----END PUBLIC KEY-----"""

# --- AUTH & LICENSING HELPERS ---

def get_product() -> str:
    product_file = os.path.join(BASE_DIR, "product.key")
    try:
        with open(product_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def verify_offline_license() -> bool:
    return True

class ActivateRequest(BaseModel):
    key: str

# --- RENDER JOB TRACKER ---

class RenderJob:
    def __init__(self, job_id: str, settings: Dict[str, Any]):
        self.job_id = job_id
        self.settings = settings
        self.status = "idle"  # idle, running, paused, cancelled, success, failed
        self.progress = 0.0
        self.status_text = "Khởi tạo..."
        self.logs: List[str] = []
        self.latest_frame_b64: Optional[str] = None
        self.output_file: Optional[str] = None
        self.start_time: float = 0.0
        self.duration: float = 0.0
        self.engine = PipelineEngine()
        self.lock = threading.Lock()

# In-memory dictionary to store active jobs
jobs_store: Dict[str, RenderJob] = {}
# Thread-safe log callbacks
ws_clients: Dict[str, List[WebSocket]] = {}

def global_log_listener(log_line: str):
    """Pushes new system logs to the logs list of all running jobs."""
    for job in jobs_store.values():
        if job.status in ["running", "paused", "success", "failed"]:
            with job.lock:
                job.logs.append(log_line)
                if len(job.logs) > 1000:
                    job.logs.pop(0)

register_log_callback(global_log_listener)

def get_r2_client():
    """Initializes and returns a boto3 client configured for Cloudflare R2."""
    if not (R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY):
        return None
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto"
    )

def upload_to_r2_and_get_presigned_url(local_filepath: str, filename: str) -> Optional[str]:
    """Uploads the rendered video file to Cloudflare R2 and returns a 2-hour pre-signed download URL."""
    try:
        s3 = get_r2_client()
        if not s3:
            logger.warning("Cloudflare R2 credentials not fully set. Skipping upload.")
            return None
            
        if not os.path.exists(local_filepath):
            logger.error(f"Rendered video file not found at {local_filepath}. Cannot upload to R2.")
            return None
            
        # Object name scheme: render_videos/<uuid>_<filename>
        object_name = f"render_videos/{uuid.uuid4()}_{filename}"
        
        logger.info(f"Uploading {local_filepath} to Cloudflare R2 bucket '{R2_BUCKET_NAME}' as '{object_name}'...")
        # Upload file
        s3.upload_file(local_filepath, R2_BUCKET_NAME, object_name)
        logger.info("Upload to R2 completed successfully.")
        
        # Generate presigned download URL for 2 hours (7200 seconds)
        presigned_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": object_name},
            ExpiresIn=7200
        )
        logger.info(f"Generated R2 pre-signed download URL.")
        return presigned_url
    except Exception as e:
        logger.error(f"Error uploading to Cloudflare R2: {e}")
        return None

async def cleanup_r2_periodically():
    """Periodically checks Cloudflare R2 bucket and deletes objects older than 12 hours."""
    logger.info("Starting R2 cleanup background task.")
    while True:
        try:
            s3 = get_r2_client()
            if s3:
                # List objects inside the bucket
                paginator = s3.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix="render_videos/")
                
                now = time.time()
                delete_keys = []
                
                for page in pages:
                    for obj in page.get('Contents', []):
                        key = obj['Key']
                        last_modified = obj['LastModified']
                        
                        last_modified_ts = last_modified.timestamp()
                        age_seconds = now - last_modified_ts
                        
                        # If older than 12 hours (12 * 3600 = 43200 seconds)
                        if age_seconds > 43200:
                            delete_keys.append({'Key': key})
                            logger.info(f"R2 object '{key}' is {age_seconds/3600:.1f} hours old. Marking for deletion.")
                            
                if delete_keys:
                    for i in range(0, len(delete_keys), 1000):
                        chunk = delete_keys[i:i+1000]
                        s3.delete_objects(
                            Bucket=R2_BUCKET_NAME,
                            Delete={'Objects': chunk}
                        )
                        logger.info(f"Deleted {len(chunk)} expired video files from Cloudflare R2.")
            else:
                logger.warning("R2 client not initialized. Cannot run R2 cleanup task.")
        except Exception as e:
            logger.error(f"Error in R2 cleanup background task: {e}")
            
        # Run every 1 hour (3600 seconds)
        await asyncio.sleep(3600)

@app.on_event("startup")
async def startup_event():
    # Start the R2 cleanup loop in the background
    asyncio.create_task(cleanup_r2_periodically())

# --- WEBHOOK NOTIFIER ---

def send_discord_webhook(job: RenderJob):
    """Sends background notifications to Discord webhook when rendering completes."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord Webhook URL not set. Skipping notification.")
        return
        
    try:
        # Calculate rendering duration
        elapsed = job.duration if job.duration > 0 else (time.time() - job.start_time)
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        if minutes > 0:
            time_str = f"{minutes} phút {seconds} giây"
        else:
            time_str = f"{seconds} giây"
            
        r2_url = None
        if job.status == "success" and job.output_file and os.path.exists(job.output_file):
            filename = os.path.basename(job.output_file)
            r2_url = upload_to_r2_and_get_presigned_url(job.output_file, filename)
            
        if job.status == "success":
            filename = os.path.basename(job.output_file) if job.output_file else "video.mp4"
            size_bytes = os.path.getsize(job.output_file) if job.output_file and os.path.exists(job.output_file) else 0
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size_bytes / 1024:.2f} KB"
                
            content = (
                f"✅ **Render thành công**\n"
                f"├── ⏱ **Thời gian render**: {time_str}\n"
                f"├── 📁 **Tên file**: `{filename}`\n"
                f"└── 📦 **Dung lượng**: `{size_str}`"
            )
        else:
            content = (
                f"❌ **Render thất bại**\n"
                f"├── ⏱ **Thời gian render**: {time_str}\n"
                f"└── ⚠️ **Lỗi**: {job.status_text}"
            )
            
        payload = {"content": content}
        
        # If R2 upload was successful and URL generated, attach a Discord Link Button
        if r2_url:
            payload["components"] = [
                {
                    "type": 1, # Action Row
                    "components": [
                        {
                            "type": 2, # Button
                            "style": 5, # Link Button
                            "label": "Tải video",
                            "url": r2_url
                        }
                    ]
                }
            ]
            
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code >= 400:
            logger.error(f"Discord Webhook returned status code {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to send Discord Webhook: {e}")


# --- API ROUTES ---

@app.get("/api/auth/status")
def auth_status():
    activated = verify_offline_license()
    return {
        "activated": activated,
        "message": "Đã kích hoạt bản quyền" if activated else "Chưa kích hoạt bản quyền"
    }

@app.post("/api/auth/activate")
def auth_activate(req: ActivateRequest):
    key = req.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Vui lòng nhập License Key!")
        
    hwid = get_hwid()
    product = get_product()
    timestamp = str(int(time.time()))
    
    # Generate verification signature matching auth.py
    raw_str = f"{key}{hwid}{timestamp}{CLIENT_SECRET_SALT}"
    signature = hashlib.sha256(raw_str.encode()).hexdigest()
    
    payload = {
        "key": key,
        "product": product,
        "hwid": hwid,
        "timestamp": timestamp,
        "signature": signature
    }
    
    try:
        resp = requests.post(WORKER_URL, json=payload, timeout=15)
        data = resp.json()
        
        if resp.status_code == 200 and data.get("success"):
            token = data.get("token")
            # Write token locally
            license_file = os.path.join(BASE_DIR, "license.key")
            with open(license_file, "w", encoding="utf-8") as f:
                f.write(token)
            return {"success": True, "message": "Kích hoạt thành công!"}
        else:
            return {"success": False, "message": data.get("message", "Khóa kích hoạt không hợp lệ.")}
    except Exception as e:
        logger.error(f"Activation request error: {e}")
        return {"success": False, "message": "Không thể kết nối tới máy chủ xác thực bản quyền."}

@app.get("/api/assets")
def list_assets():
    """Lists standard/custom background textures and brushes available on the server."""
    # List backgrounds
    bg_dir = os.path.join(ASSETS_DIR, "backgrounds")
    backgrounds = ["Whiteboard", "Blackboard", "Old Paper", "Canvas", "Paper Texture"]
    if os.path.exists(bg_dir):
        for f in os.listdir(bg_dir):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                backgrounds.append(f)
                
    # List brushes
    brush_dir = os.path.join(ASSETS_DIR, "brushes")
    brushes = ["Pencil", "Ink Pen", "Marker", "Brush"]
    if os.path.exists(brush_dir):
        for f in os.listdir(brush_dir):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                brushes.append(f)
                
    return {
        "backgrounds": list(set(backgrounds)),
        "brushes": list(set(brushes))
    }

@app.get("/api/voices")
async def list_voices():
    """Gets cached list of edge-tts and capcut speakers."""
    edge_gen = EdgeTTSGenerator()
    capcut_gen = CapCutTTSGenerator()
    
    edge_voices = await edge_gen.get_all_voices()
    capcut_voices = capcut_gen.get_all_voices()
    
    return {
        "edge": edge_voices,
        "capcut": capcut_voices
    }

@app.post("/api/upload/{upload_type}")
async def upload_file(upload_type: str, file: UploadFile = File(...)):
    """Handles asset uploading: scenes, bgm, logos, custom brushes, backgrounds."""
    if upload_type not in ["image", "bgm", "logo", "brush", "background"]:
        raise HTTPException(status_code=400, detail="Loại upload không hợp lệ.")
        
    ext = os.path.splitext(file.filename)[1].lower()
    uuid_name = f"{uuid.uuid4()}{ext}"
    
    # Save folder definition
    if upload_type == "image":
        dest_dir = os.path.join(UPLOAD_DIR, "scene_images")
        url_prefix = "/static/uploads/scene_images"
    elif upload_type == "bgm":
        dest_dir = os.path.join(UPLOAD_DIR, "bgm")
        url_prefix = "/static/uploads/bgm"
    elif upload_type == "logo":
        dest_dir = os.path.join(UPLOAD_DIR, "logos")
        url_prefix = "/static/uploads/logos"
    elif upload_type == "brush":
        dest_dir = os.path.join(ASSETS_DIR, "brushes")
        url_prefix = "/static/assets/brushes"
    elif upload_type == "background":
        dest_dir = os.path.join(ASSETS_DIR, "backgrounds")
        url_prefix = "/static/assets/backgrounds"
        
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, uuid_name)
    
    try:
        with open(dest_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        return {
            "success": True,
            "filename": file.filename,
            "path": dest_path,
            "url": f"{url_prefix}/{uuid_name}"
        }
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể lưu file: {str(e)}")

class RenderRequest(BaseModel):
    settings: Dict[str, Any]

@app.post("/api/render/start")
def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    """Starts the video generation job."""
    # Check license before rendering
    if not verify_offline_license():
        raise HTTPException(status_code=403, detail="Bản quyền chưa được kích hoạt hoặc đã hết hạn!")
        
    job_id = str(uuid.uuid4())
    settings = req.settings
    
    # Initialize RenderJob tracker
    job = RenderJob(job_id, settings)
    jobs_store[job_id] = job
    
    # Setup background thread generation callbacks
    def progress_cb(fraction: float, status_text: str):
        with job.lock:
            job.progress = fraction
            job.status_text = status_text
            
    def preview_cb(pil_img: Image.Image):
        # Convert PIL to JPEG base64 to stream over Websockets
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        buffered = io.BytesIO()
        pil_img.save(buffered, format="JPEG", quality=65)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        with job.lock:
            job.latest_frame_b64 = img_str
            
    def finished_cb(success: bool, message: str):
        with job.lock:
            job.status = "success" if success else "failed"
            job.status_text = message
            job.duration = time.time() - job.start_time
            if success:
                # Find output file inside outputs directory
                # Filename scheme matches: drawing_video_*.mp4
                out_files = sorted(
                    [os.path.join(OUTPUT_DIR, f) for f in os.listdir(OUTPUT_DIR) if f.startswith("drawing_video_") and f.endswith(".mp4")],
                    key=os.path.getmtime
                )
                if out_files:
                    job.output_file = out_files[-1]
            
        logger.info(f"Job {job_id} finished. Status: {job.status}. Message: {message}")
        # Trigger Discord webhook notification directly inside the generator thread
        try:
            send_discord_webhook(job)
        except Exception as e:
            logger.error(f"Failed to call send_discord_webhook: {e}")
        
    # Standardize export directory to backend output folder
    settings["export_dir"] = OUTPUT_DIR
    
    # Rewrite relative urls/paths for scene images, bgms, logos to local absolute paths
    for sc in settings.get("scenes", []):
        img_p = sc.get("image_path", "")
        if img_p.startswith("/static/"):
            sc["image_path"] = translate_url_to_path(img_p)
            
    bgm_p = settings.get("music_path", "")
    if bgm_p.startswith("/static/"):
        settings["music_path"] = translate_url_to_path(bgm_p)
        
    pen_p = settings.get("pen_style", "")
    if pen_p.startswith("/static/"):
        settings["pen_style"] = translate_url_to_path(pen_p)
        
    bg_p = settings.get("bg_style", "")
    if bg_p.startswith("/static/"):
        settings["bg_style"] = translate_url_to_path(bg_p)
        
    for logo in settings.get("logos", []):
        l_path = logo.get("path", "")
        if l_path.startswith("/static/"):
            logo["path"] = translate_url_to_path(l_path)
            
    # Launch pipeline engine thread
    job.status = "running"
    job.start_time = time.time()
    job.engine.start_generation(settings, progress_cb, preview_cb, finished_cb)
    
    return {"success": True, "job_id": job_id}

def translate_url_to_path(url: str) -> str:
    """Translates static mount URLs back to local absolute file paths."""
    if url.startswith("/static/uploads/"):
        rel = url.replace("/static/uploads/", "")
        return os.path.join(UPLOAD_DIR, rel.replace("/", os.sep))
    elif url.startswith("/static/assets/"):
        rel = url.replace("/static/assets/", "")
        return os.path.join(ASSETS_DIR, rel.replace("/", os.sep))
    elif url.startswith("/static/output/"):
        rel = url.replace("/static/output/", "")
        return os.path.join(OUTPUT_DIR, rel.replace("/", os.sep))
    return url

@app.post("/api/render/pause/{job_id}")
def pause_render(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    job.engine.pause()
    job.status = "paused"
    return {"success": True, "status": "paused"}

@app.post("/api/render/resume/{job_id}")
def resume_render(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    job.engine.resume()
    job.status = "running"
    return {"success": True, "status": "running"}

@app.post("/api/render/cancel/{job_id}")
def cancel_render(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    job.engine.cancel()
    job.status = "cancelled"
    return {"success": True, "status": "cancelled"}

@app.get("/api/render/status/{job_id}")
def query_render_status(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job không tồn tại.")
    with job.lock:
        download_url = None
        if job.status == "success" and job.output_file:
            download_url = f"/api/download/{os.path.basename(job.output_file)}"
            
        return {
            "job_id": job.job_id,
            "status": job.status,
            "progress": job.progress,
            "status_text": job.status_text,
            "download_url": download_url
        }

@app.get("/api/download/{filename}")
def download_video(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File không tồn tại.")
    return FileResponse(path, media_type="video/mp4", filename=filename)

@app.get("/api/history")
def list_history():
    """Lists history of previously generated videos inside the output folder."""
    if not os.path.exists(OUTPUT_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")],
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
        reverse=True
    )
    history = []
    for f in files:
        path = os.path.join(OUTPUT_DIR, f)
        history.append({
            "filename": f,
            "size": os.path.getsize(path),
            "created_at": os.path.getmtime(path),
            "download_url": f"/api/download/{f}"
        })
    return history

# --- WEBSOCKET EVENT ENGINE ---

@app.websocket("/ws/render")
async def ws_render_monitor(websocket: WebSocket):
    await websocket.accept()
    query_params = websocket.query_params
    job_id = query_params.get("job_id")
    
    if not job_id or job_id not in jobs_store:
        await websocket.send_json({"error": "Mã Job không hợp lệ."})
        await websocket.close()
        return
        
    job = jobs_store[job_id]
    logger.info(f"WebSocket client connected to monitor Job {job_id}")
    
    # Stream render progress, ETA, frames, and console logs loop
    last_log_idx = 0
    try:
        while True:
            # Poll status & build update payload
            with job.lock:
                # Get new logs since last loop index
                new_logs = job.logs[last_log_idx:]
                last_log_idx = len(job.logs)
                
                # Estimate time elapsed and ETA
                elapsed = time.time() - job.start_time if job.status in ["running", "paused"] else job.duration
                if job.progress > 0:
                    total_est = elapsed / job.progress
                    eta = max(0, int(total_est - elapsed))
                else:
                    eta = 0
                    
                payload = {
                    "job_id": job.job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "status_text": job.status_text,
                    "eta_seconds": eta,
                    "elapsed_seconds": int(elapsed),
                    "new_logs": new_logs,
                    "preview_frame": job.latest_frame_b64
                }
                
                # Clear preview frame after reading to save bandwidth
                job.latest_frame_b64 = None
                
            await websocket.send_json(payload)
            
            # If job is finalized, wait a few seconds and exit loop
            if job.status in ["success", "failed", "cancelled"]:
                # Send one last check and close connection
                await asyncio.sleep(2)
                break
                
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from Job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error for Job {job_id}: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    # Use HF Space default port 7860
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=True)
