# main.py
#main
import os, uuid, subprocess, json, shutil, glob, mimetypes
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Request, Form, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
# --- Imaging ---
from PIL import Image
from io import BytesIO

# --- S3 deps ---
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# --- CV2 for blur scoring ---
import cv2
import numpy as np

from style_presets import SCENE_SETTINGS, SCENE_DETAIL, PRESENTER_STYLES, PRESENTER_DETAIL
from chunker import split_script
from models import JobStatus
from veo_pollo_client import PolloClient
load_dotenv()
APP_DIR = os.path.dirname(__file__)
DATA_DIR = os.getenv("JOB_DATA_DIR", os.path.join(APP_DIR, "_jobs"))
os.makedirs(DATA_DIR, exist_ok=True)

# ---------- tuning ----------
TARGET_FPS = 24
TARGET_FRAMES = 192
# CHANGED: best-of-last 4 frames only
CANDIDATE_RANGE = (189, 192)   # inclusive: 189, 190, 191, 192

NEGATIVE_PROMPT = os.getenv(
    "NEGATIVE_PROMPT",
    "Camera switch, zoom in, zoom out, moving frames, subtitles, text overlays, captions, "
    "blur, soft focus, watercolor edges, posterization, "
    "music, musical instruments, logo slates, splash screens, montage, jump cuts, "
    "subtitles, floating captions, watermarks, warped hands, "
    "title card, standalone product photo"
)

# Optional fixed seed for per-run consistency
FIXED_SEED = os.getenv("VEO_SEED")
FIXED_SEED = int(FIXED_SEED) if (FIXED_SEED is not None and str(FIXED_SEED).strip() != "") else None

# ---------- S3 configuration ----------
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
S3_BUCKET  = os.getenv("S3_BUCKET", "emotion-detection1")
S3_PREFIX  = os.getenv("S3_PREFIX", "vidgen/frames")
s3 = boto3.client("s3", region_name=AWS_REGION)

def s3_public_url(bucket: str, key: str, region: str = AWS_REGION) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

def upload_public_png(local_path: str, key: str) -> str:
    # Bucket should be “Bucket owner enforced”; ACL not required
    s3.upload_file(local_path, S3_BUCKET, key, ExtraArgs={"ContentType": "image/png"})
    return s3_public_url(S3_BUCKET, key)

# ---------- Gemini upscaling (from main_with upscaling.py) ----------
UPSCALE_FRAMES = os.getenv("UPSCALE_FRAMES", "true").lower() in ("1", "true", "yes", "on")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image-preview")
GEMINI_PROMPT = os.getenv(
    "GEMINI_UPSCALE_PROMPT",
    """Enhance this image to 4K resolution. Improve clarity and sharpness in all blurred areas (especially the face, eyes, and hands) while keeping the subject’s exact likeness, pose, clothing, and background unchanged. Maintain natural colors, lighting, and framing. Avoid adding new elements, artifacts, or stylization. The result should look photorealistic, clean, and naturally sharp."""
)

def gemini_upscale_image(frame_path: str, out_path: str) -> bool:
    """
    Uses google-genai ('google.genai') streaming to produce a single enhanced image.
    Returns True if an image was produced and saved to out_path.
    """
    if not UPSCALE_FRAMES:
        return False
    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        print(f"[gemini] SDK import failed, skipping upscale: {e}")
        return False
    

    
    api_key = os.environ.get("GEMINI_API_KEY")
    print(api_key)
    if not api_key:
        print("[gemini] GEMINI_API_KEY not set; skipping upscale")
        return False

    mime_type, _ = mimetypes.guess_type(frame_path)
    mime_type = mime_type or "image/png"
    with open(frame_path, "rb") as f:
        frame_bytes = f.read()

    client = genai.Client(api_key=api_key)
    parts = [
        types.Part.from_text(text=GEMINI_PROMPT),
        types.Part.from_bytes(mime_type=mime_type, data=frame_bytes),
    ]
    contents = [types.Content(role="user", parts=parts)]
    config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])

    image_bytes: Optional[bytes] = None
    try:
        for chunk in client.models.generate_content_stream(
            model=GEMINI_MODEL, contents=contents, config=config
        ):
            if (
                getattr(chunk, "candidates", None)
                and chunk.candidates[0].content
                and chunk.candidates[0].content.parts
                and getattr(chunk.candidates[0].content.parts[0], "inline_data", None)
                and getattr(chunk.candidates[0].content.parts[0].inline_data, "data", None)
            ):
                image_bytes = chunk.candidates[0].content.parts[0].inline_data.data
                break
        if image_bytes:
            with open(out_path, "wb") as f_out:
                f_out.write(image_bytes)
            print(f"[gemini] upscale saved -> {out_path}")
            return True
        print("[gemini] no image in stream; skipping upscale")
        return False
    except Exception as e:
        print(f"[gemini] upscale failed: {e}")
        return False

# ---------- 4K pre-upscale with Pillow ----------
TARGET_WIDTH = 3840
TARGET_HEIGHT = 2160

def save_and_upscale(image_bytes: bytes, output_file: str):
    """Save image and upscale to 3840x2160 using Pillow (LANCZOS)."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    # Pillow docs recommend Image.Resampling.LANCZOS for high-quality scaling.
    # https://pc-pillow.readthedocs.io/.../Image_resize.html
    img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    img.save(output_file, "PNG")
    print(f"Saved upscaled image to: {output_file}")

# ---------- FastAPI ----------
app = FastAPI(title="Veo 3 Fast – Video Generation Pipeline (continuity from best tail frame + 4K+Gemini)")
app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(APP_DIR, "templates"))
JOBS: Dict[str, Dict] = {}

# ---------- ffmpeg helpers ----------
def _run_ffmpeg(args: List[str]):
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args, p.stdout, p.stderr)

def extract_frames_exact_192(in_video: str, out_dir: str):
    """Extract frames at TARGET_FPS and coerce to exactly 192 frames (pad/crop if needed)."""
    ensure_dir(out_dir)
    # clean any old frames
    for p in glob.glob(os.path.join(out_dir, "*.png")):
        os.remove(p)
    pattern = os.path.join(out_dir, "%06d.png")
    _run_ffmpeg([
        "-i", in_video,
        "-vf", f"fps={TARGET_FPS}",
        "-vsync", "0",
        pattern
    ])
    files = sorted(glob.glob(os.path.join(out_dir, "*.png")))
    count = len(files)
    if count < TARGET_FRAMES and count > 0:
        last = files[-1]
        for i in range(count + 1, TARGET_FRAMES + 1):
            shutil.copyfile(last, os.path.join(out_dir, f"{i:06d}.png"))
    elif count > TARGET_FRAMES:
        for i in range(TARGET_FRAMES + 1, count + 1):
            p = os.path.join(out_dir, f"{i:06d}.png")
            if os.path.exists(p):
                os.remove(p)

def extract_audio(in_path: str, out_audio_path: str):
    _run_ffmpeg(["-i", in_path, "-vn", "-ac", "2", "-ar", "48000",
                 "-c:a", "aac", "-b:a", "128k", out_audio_path])

def write_concat_file(paths: List[str], list_path: str):
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths: f.write("file '{}'\n".format(p.replace("\\", "/")))

def concat_audio_to_m4a(audio_paths: List[str], out_path: str):
    tmp_list = os.path.join(os.path.dirname(out_path), "audio_concat.txt")
    write_concat_file(audio_paths, tmp_list)
    _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", tmp_list,
                 "-c:a", "aac", "-b:a", "128k", out_path])

def encode_video_from_frames(frames_dir: str, out_path: str, fps: int = TARGET_FPS):
    _run_ffmpeg(["-framerate", str(fps), "-i", os.path.join(frames_dir, "%06d.png"),
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), out_path])

def mux_frames_with_audio(frames_dir: str, audio_path: str, out_path: str, fps: int = TARGET_FPS):
    _run_ffmpeg(["-framerate", str(fps), "-i", os.path.join(frames_dir, "%06d.png"),
                 "-i", audio_path, "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                 "-c:a", "aac", "-b:a", "128k", "-shortest", out_path])

# ---------- frame utilities ----------
def ensure_dir(d: str): os.makedirs(d, exist_ok=True)
def frame_path(frames_dir: str, idx: int) -> str: return os.path.join(frames_dir, f"{idx:06d}.png")

def copy_frames(src_dir: str, dst_dir: str, start_idx: int, end_idx: int, start_at: int = 1) -> int:
    ensure_dir(dst_dir); w = start_at
    for i in range(start_idx, end_idx + 1):
        shutil.copyfile(frame_path(src_dir, i), frame_path(dst_dir, w))
        w += 1
    return w

def calculate_blur_score(image_path: str) -> Optional[float]:
    img = cv2.imread(image_path)
    if img is None: return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def pick_best_from_candidates(frames_dir: str, cand_dir: str, start_idx: int = 189, end_idx: int = 192) -> Tuple[int, float, str]:
    """Copy candidate frames (start..end) to cand_dir, compute blur scores, return (best_idx, score, best_path)."""
    ensure_dir(cand_dir)
    best_idx, best_score, best_path = start_idx, -1.0, ""
    for i in range(start_idx, end_idx + 1):
        src = frame_path(frames_dir, i)
        dst = os.path.join(cand_dir, f"{i:06d}.png")
        shutil.copyfile(src, dst)
        s = calculate_blur_score(dst) or -1.0
        if s > best_score:
            best_idx, best_score, best_path = i, s, dst
    return best_idx, best_score, best_path

# ---------- Prompt helpers ----------
def _http_image_or_none(url: str) -> Optional[str]:
    u = (url or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else None

def build_prompt(
    brand: str,
    product: str,
    scene_key: str,
    presenter_key: str,
    text: str,
    is_first: bool = False,
    is_last: bool = False
) -> str:
    scene = SCENE_DETAIL[scene_key]
    persona = PRESENTER_DETAIL[presenter_key]
    static_rules = "Keep camera and framing static and consistent across shots. "
    if is_first:
        prefix = f"Open directly inside a {scene['env']}. Analyse the product then blend the presenter and product accordingly: "  
        f"If the product  is holdable, then presenter ({persona['persona']}) is holding the {product}."
        f"If the product  is wearable, then presenter ({persona['persona']}) is wearing the {product}."
        f"If the product  is placeable, then {product} is placed besides the presenter ({persona['persona']})."
    else:
        prefix = f"{brand} {product} promo. {persona['persona']} in a {scene['env']}. "
    base = (
        f"{prefix}"
        f"{static_rules}"
        f"Lighting: {scene['lighting']}. "
        f"Presenter faces camera and presenter's body must be visible till knees and clearly says: \"{text}\" "
        f"Presenter's skin must be clear."
        f"Voice: {persona['voice']}. Delivery: {persona['delivery']}. "
        f"Keep same identity, outfit, static framing, and environment as the reference image. "
    )
    if is_last:
        base += " End by holding the product centered for 1s, label sharp."
    return " ".join(base.split())

# ---------- Worker ----------
def process_job(job_id: str):
    job = JOBS[job_id]
    req = job["req"]
    out_dir = job["dir"]
    os.makedirs(out_dir, exist_ok=True)

    # 1) Script → chunks
    chunks = split_script(req["marketing_script"], req["speaking_wps"], 8.0, 3.0)
    job["chunks"] = chunks
    job["prompts"] = []
    errors: List[str] = []
    JOBS[job_id]["status"] = "chunked"

    pc = PolloClient()

    # First continuity image: product image (uploaded-file-to-S3 preferred, else URL)
    next_image_url: Optional[str] = _http_image_or_none(req.get("product_image_url"))

    # Master frames
    frames_master = os.path.join(out_dir, "frames_master")
    ensure_dir(frames_master)
    master_next_idx = 1

    # Per-chunk audio for final concat
    audio_parts: List[str] = []

    # Generate each chunk
    JOBS[job_id]["status"] = "generating"
    total = max(1, len(chunks))

    try:
        for i, text in enumerate(chunks, start=1):
            JOBS[job_id]["status"] = f"generating {i}/{total}"

            prompt = build_prompt(
                req["brand"], req["product"],
                req["scene_setting"], req["presenter_style"],
                text,
                is_first=(i == 1),
                is_last=(i == total)
            )
            job["prompts"].append(prompt)

            raw_chunk_path = os.path.join(out_dir, f"scene_{i:02d}_raw.mp4")

            # Per-chunk working dirs
            frames_dir = os.path.join(out_dir, f"frames_{i:02d}")
            frames_trim_dir = os.path.join(out_dir, f"frames_trim_{i:02d}")
            cand_dir = os.path.join(out_dir, f"candidates_{i:02d}")
            ensure_dir(frames_dir); ensure_dir(frames_trim_dir); ensure_dir(cand_dir)

            # Snapshot the exact image URL we are about to send
            image_url_to_send = next_image_url

            # --- Create Task (payload shown on status page) ---
            create = pc.generate_veo_fast(
                prompt=prompt,
                image_url=image_url_to_send,
                length=8,
                aspect="16:9",
                resolution="1080p",
                seed=FIXED_SEED,
                generate_audio=True,
                negative_prompt=NEGATIVE_PROMPT
            )
            try:
                job.setdefault("payloads", []).append(json.dumps(create.get("payload", {}), indent=2))
            except Exception:
                job.setdefault("payloads", []).append(json.dumps({"_debug": "no payload captured"}, indent=2))

            task_id = create.get("taskId")
            if not task_id:
                raise RuntimeError(f"Missing taskId in Pollo response: {create}")

            final = pc.poll_task(task_id)
            video_url = final.get("url")
            if not video_url:
                raise RuntimeError(f"No video url in final: {final}")

            pc.download_file(video_url, raw_chunk_path)

            # Extract normalized frames (exactly 192)
            extract_frames_exact_192(raw_chunk_path, frames_dir)
            errors.append(f"INFO scene {i}: extracted original frames -> {frames_dir}")

            # Candidate selection from frames 189..192
            best_idx, best_score, best_png = pick_best_from_candidates(frames_dir, cand_dir, *CANDIDATE_RANGE)
            errors.append(f"INFO scene {i}: best tail frame index={best_idx} (189–192), score={best_score:.2f}")

            # Build frames_trim by copying 1..best_idx, then copying previous D frames to keep 192 total
            D = TARGET_FRAMES - best_idx
            write_idx = copy_frames(frames_dir, frames_trim_dir, 1, best_idx, start_at=1)
            if D > 0:
                start_copy = max(1, best_idx - D)
                write_idx = copy_frames(frames_dir, frames_trim_dir, start_copy, best_idx - 1, start_at=write_idx)
                errors.append(
                    f"INFO scene {i}: dropped frames {best_idx+1}..{TARGET_FRAMES} (count={D}); "
                    f"copied frames {start_copy}..{best_idx-1} to keep total at {TARGET_FRAMES}"
                )

            # --- NEW: 4K Pillow upscale -> Gemini upscale -> upload -> use as NEXT ref image
            try:
                with open(best_png, "rb") as f_in:
                    raw_bytes = f_in.read()

                cont_4k = os.path.join(out_dir, f"scene_{i:02d}_cont_4k.png")
                save_and_upscale(raw_bytes, cont_4k)  # 3840x2160 via Pillow

                cont_4k_gem = os.path.join(out_dir, f"scene_{i:02d}_cont_4k_gemini.png")
                used_path = cont_4k
                if UPSCALE_FRAMES and gemini_upscale_image(cont_4k, cont_4k_gem):
                    used_path = cont_4k_gem

                key = f"{S3_PREFIX}/{job_id}/scene_{i:02d}_cont.png"
                next_image_url = upload_public_png(used_path, key)
                errors.append(f"INFO scene {i}: continuity frame (4K→Gemini) -> https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}")
            except (BotoCoreError, ClientError, subprocess.CalledProcessError, OSError) as e:
                errors.append(f"S3/Gemini continuity step failed for scene {i}: {e}")

            # Extract audio for this chunk (8s) for later concatenation
            audio_i = os.path.join(out_dir, f"scene_{i:02d}.m4a")
            extract_audio(raw_chunk_path, audio_i)
            audio_parts.append(audio_i)
            errors.append(f"INFO scene {i}: extracted audio -> {audio_i}")

            # Append trimmed frames into master sequence
            master_next_idx = copy_frames(frames_trim_dir, frames_master, 1, TARGET_FRAMES, start_at=master_next_idx)

            job["progress"] = i / total

    except Exception as e:
        errors.append(f"FATAL: {e}")
        job["errors"] = errors
        JOBS[job_id]["status"] = "failed"
        return

    # Final mux: frames_master + concatenated audio
    JOBS[job_id]["status"] = "concatenating"
    final_16x9 = os.path.join(out_dir, f"{job_id}_final_16x9.mp4")
    try:
        if audio_parts:
            audio_all = os.path.join(out_dir, "audio_all.m4a")
            concat_audio_to_m4a(audio_parts, audio_all)
            errors.append(f"INFO: concatenated audio parts -> {audio_all}")
            mux_frames_with_audio(frames_master, audio_all, final_16x9, fps=TARGET_FPS)
        else:
            encode_video_from_frames(frames_master, final_16x9, fps=TARGET_FPS)
        errors.append(f"INFO: final video built from frames -> {final_16x9}")

        JOBS[job_id]["status"] = "done"
        job["video_path"] = final_16x9
        job["errors"] = errors or None
    except Exception as e:
        errors.append(str(e))
        job["errors"] = errors
        JOBS[job_id]["status"] = "failed"

# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "scene_settings": SCENE_SETTINGS,
        "presenter_styles": PRESENTER_STYLES,
        "jobs": JOBS
    })

@app.post("/generate")
async def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    brand: str = Form(...),
    product: str = Form(...),
    product_image_url: str = Form(""),
    product_image_file: UploadFile = File(None),           # NEW: optional file upload
    marketing_script: str = Form(...),
    speaking_wps: float = Form(4.2),
    scene_setting: str = Form(...),
    presenter_style: str = Form(...),
):
    job_id = "job_" + uuid.uuid4().hex[:10]
    out_dir = os.path.join(DATA_DIR, job_id)
    os.makedirs(out_dir, exist_ok=True)

    # If the user uploaded a file, convert to PNG, push to S3 immediately, and use that URL.
    uploaded_url = ""
    if product_image_file and product_image_file.filename:
        try:
            raw = await product_image_file.read()
            # Convert any incoming image to PNG for consistent content-type on S3
            local_png = os.path.join(out_dir, "product_upload.png")
            Image.open(BytesIO(raw)).convert("RGB").save(local_png, "PNG")
            s3_key = f"{S3_PREFIX}/{job_id}/product_upload.png"
            uploaded_url = upload_public_png(local_png, s3_key)
        except Exception as e:
            # Fallback silently to provided URL if upload fails
            print(f"[upload] product file upload failed: {e}")

    # Prefer uploaded file URL; else fall back to raw URL field
    first_ref_url = (uploaded_url or product_image_url or "").strip()

    JOBS[job_id] = {
        "status": "queued",
        "dir": out_dir,
        "req": {
            "brand": brand.strip(),
            "product": product.strip(),
            "product_image_url": first_ref_url,   # keep same key so pipeline doesn't need special-casing
            "marketing_script": marketing_script.strip(),
            "speaking_wps": float(speaking_wps),
            "scene_setting": scene_setting,
            "presenter_style": presenter_style,
        },
        "progress": 0.0,
        "payloads": [],
        "prompts": [],
        "errors": []
    }
    background_tasks.add_task(process_job, job_id)
    return RedirectResponse(url=f"/status/{job_id}", status_code=303)

@app.get("/status/{job_id}", response_class=HTMLResponse)
async def status_page(job_id: str, request: Request):
    job = JOBS.get(job_id)
    if not job:
        return HTMLResponse(f"<h3>Job {job_id} not found</h3>", status_code=404)
    return templates.TemplateResponse("status.html", {"request": request, "job_id": job_id, "job": job})

@app.get("/api/status/{job_id}", response_model=JobStatus)
async def status_api(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return JobStatus(
        job_id=job_id,
        status=job.get("status", "unknown"),
        message="; ".join(job.get("errors", [])) if job.get("errors") else None,
        chunks=job.get("chunks"),
        video_path=job.get("video_path"),
        prompts=job.get("prompts"),
        payloads=job.get("payloads"),
    )

@app.get("/download/{job_id}")
async def download(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("video_path") or not os.path.exists(job["video_path"]):
        return JSONResponse(status_code=404, content={"detail": "not ready"})
    return FileResponse(job["video_path"], filename=os.path.basename(job["video_path"]))