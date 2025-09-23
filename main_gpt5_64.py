import os, uuid, subprocess, json, shutil, glob, mimetypes, time
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, Request, Form, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from style_presets import SCENE_SETTINGS, SCENE_DETAIL, PRESENTER_STYLES, PRESENTER_DETAIL
from chunker import split_script
from models import JobStatus
from veo_pollo_client import PolloClient
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import cv2
import numpy as np
import json
import base64

try:
    import openai
except Exception:
    openai = None

load_dotenv()
APP_DIR = os.path.dirname(__file__)
DATA_DIR = os.getenv("JOB_DATA_DIR", os.path.join(APP_DIR, "_jobs"))
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_FPS = 24
TARGET_FRAMES = 192
CANDIDATE_RANGE = (189, 192)

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
# Maximum image bytes to embed as data URI (default 256 KB)
MAX_EMBED_BYTES = int(os.getenv("MAX_EMBED_BYTES", str(256 * 1024)))


def s3_public_url(bucket: str, key: str, region: str = AWS_REGION) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

def upload_public_png(local_path: str, key: str) -> str:
    # Bucket should be “Bucket owner enforced”; ACL not required
    s3.upload_file(local_path, S3_BUCKET, key, ExtraArgs={"ContentType": "image/png"})
    return s3_public_url(S3_BUCKET, key)

# ---------- Gemini upscaling (updated to accept dynamic prompt) ----------
UPSCALE_FRAMES = os.getenv("UPSCALE_FRAMES", "true").lower() in ("1", "true", "yes", "on")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image-preview")

def gemini_upscale_image(frame_path: str, out_path: str, prompt_text: str) -> bool:
    """
    Uses google-genai ('google.genai') streaming to produce a single enhanced image using a dynamic prompt.
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
    if not api_key:
        print("[gemini] GEMINI_API_KEY not set; skipping upscale")
        return False

    mime_type, _ = mimetypes.guess_type(frame_path)
    mime_type = mime_type or "image/png"
    with open(frame_path, "rb") as f:
        frame_bytes = f.read()

    client = genai.Client(api_key=api_key)
    parts = [
        types.Part.from_text(text=prompt_text),
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

# ---------- FastAPI ----------
app = FastAPI(title="Veo 3 Fast – Video Generation Pipeline (dynamic GPT5 -> Gemini upscaling)")
app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(APP_DIR, "templates"))
JOBS: Dict[str, Dict] = {}

# ---------- ffmpeg helpers ----------
import json
import os
from datetime import datetime

# Log file path (create a logs directory if it doesn't exist)
LOG_DIR = os.path.join(APP_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_gpt_response(job_id: str, response: dict, prompt: str, response_type: str):
    """
    Logs GPT response to a file for debugging.

    :param job_id: Unique job ID for reference
    :param response: GPT response
    :param prompt: The prompt that generated the response
    :param response_type: Type of the response (e.g., 'upscale', 'similarity_check')
    """
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "job_id": job_id,
        "response_type": response_type,
        "prompt": prompt,
        "response": response,
    }

    log_filename = os.path.join(LOG_DIR, f"{job_id}_{response_type}_response_log.json")
    
    with open(log_filename, "a") as log_file:
        json.dump(log_data, log_file, indent=2)
        log_file.write("\n")

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

# ---------- GPT-5 helpers ----------
MAX_GPT_RETRIES = int(os.getenv("MAX_GPT_RETRIES", "3"))
MAX_GEMINI_RETRIES = int(os.getenv("MAX_GEMINI_RETRIES", "2"))

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if openai and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# ----- Robust GPT-5 helpers (Responses API preferred, ChatCompletion fallback) -----
import traceback
import time

def _extract_text_from_openai_resp(resp) -> Optional[str]:
    """
    Try multiple common response shapes: Responses API and ChatCompletion API.
    Returns stripped text or None.
    """
    try:
        # Responses API (openai.responses.create)
        if isinstance(resp, dict) and resp.get("output"):
            # New Responses API sometimes stores text in output[0].content[0].text
            out = resp.get("output")
            if isinstance(out, list) and len(out) > 0:
                # try structured places
                for item in out:
                    if isinstance(item, dict) and item.get("content"):
                        for part in item["content"]:
                            if isinstance(part, dict) and part.get("text"):
                                t = part["text"]
                                if t and str(t).strip():
                                    return str(t).strip()
                # last chance: top-level output_text
            if resp.get("output_text"):
                t = resp.get("output_text")
                return t.strip() if t and str(t).strip() else None

        # ChatCompletion API shape
        if "choices" in resp and len(resp["choices"]) > 0:
            choice = resp["choices"][0]
            # common: choice['message']['content']
            msg = choice.get("message") or {}
            c = msg.get("content") or msg.get("text") or choice.get("text")
            if c and str(c).strip():
                return str(c).strip()
    except Exception:
        # fallback to None
        pass
    return None

def _make_data_uri_from_file(path: str) -> Optional[str]:
    """Return data:image/png;base64,... if file small enough, else None."""
    try:
        if not os.path.exists(path):
            return None
        size = os.path.getsize(path)
        if size > MAX_EMBED_BYTES:
            # too big to embed
            return None
        with open(path, "rb") as f:
            b = f.read()
        b64 = base64.b64encode(b).decode("ascii")
        # try to guess mime type
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "image/png"
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[embed] failed to make data uri for {path}: {e}")
        return None

def _ensure_image_accessible(job_id: str, path_or_url: str, s3_key_prefix: str = None) -> str:
    """
    If path_or_url is an http(s) URL -> return it.
    If it's a local path and small -> return data URI.
    If it's a local path and too large -> upload to S3 and return public URL.
    """
    if not path_or_url:
        return ""
    # already a URL
    if str(path_or_url).lower().startswith(("http://", "https://")):
        return path_or_url
    # local file path
    local = str(path_or_url)
    data_uri = _make_data_uri_from_file(local)
    if data_uri:
        return data_uri
    # otherwise upload to S3 and return URL
    try:
        # if caller didn't provide custom key prefix, use S3_PREFIX/job_id
        filename = os.path.basename(local)
        key_name = f"{S3_PREFIX}/{job_id}/{s3_key_prefix or 'gpt_embedded'}/{filename}"
        url = upload_public_png(local, key_name)
        return url
    except Exception as e:
        print(f"[embed] upload fallback failed for {local}: {e}")
        return local  # last resort return local path (GPT may not access)

def call_gpt5_for_upscale_prompt(job_id: str, system_prompt: str, user_prompt: str, image_paths_or_urls: List[str]) -> Optional[str]:
    """
    Prepare images (embed small ones as data URIs or upload large ones to S3),
    send system+user to GPT-5 and return the generated upscaling prompt text.
    Logs full raw response via log_gpt_response.
    """
    if openai is None or not OPENAI_API_KEY:
        print("[gpt5-upscale] openai client or OPENAI_API_KEY missing")
        return None

    # Prepare accessible image references (data URIs or URLs)
    prepared = []
    for idx, p in enumerate(image_paths_or_urls or []):
        try:
            ref = _ensure_image_accessible(job_id, p, s3_key_prefix=f"image_{idx+1}")
            prepared.append(ref)
        except Exception as e:
            print(f"[gpt5-upscale] prepare image failed for {p}: {e}")
            prepared.append(str(p))

    # Build user text (compact)
    img_text = "\n".join(f"Image {i+1}: {u}" for i, u in enumerate(prepared))
    combined_user = user_prompt + "\n\n" + img_text + "\n\n" \
                    "IMPORTANT: Output exactly one concise prompt optimized for an image upscaler. Do not include any explanations."

    prompt_for_log = combined_user  # used for logging

    try:
        # Use chat completion as in your working script (no tiny max_tokens)
        resp = openai.ChatCompletion.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_user}
            ],
            temperature=0.0,
            max_tokens=1024
        )
        # log full raw response
        try:
            log_gpt_response(job_id, resp, prompt_for_log, "upscale_gpt_raw")
        except Exception:
            print("[gpt5-upscale] warning: failed to log response")

        # extract text robustly
        txt = None
        try:
            txt = _extract_text_from_openai_resp(resp)
        except Exception:
            # fallback extraction
            try:
                txt = resp['choices'][0]['message'].get('content', "")
            except Exception:
                txt = None

        if txt:
            txt = txt.strip()
            print("[gpt5-upscale] extracted text:", txt)
            return txt
        else:
            print("[gpt5-upscale] WARNING: no content in GPT response")
            return None
    except Exception as e:
        print(f"[gpt5-upscale] error: {e}")
        try:
            log_gpt_response(job_id, {"error": str(e)}, prompt_for_log, "upscale_gpt_error")
        except Exception:
            pass
    return None


def call_gpt5_for_similarity_check(job_id: str, system_prompt: str, user_prompt: str, upscaled_path_or_url: str, original_path_or_url: str) -> Optional[bool]:
    """
    Send both images (embedded if small) directly in the user message and request a one-word 'yes' or 'no'.
    Logs raw response.
    """
    if openai is None or not OPENAI_API_KEY:
        print("[gpt5-check] openai client or OPENAI_API_KEY missing")
        return None

    # Prepare references
    up_ref = _ensure_image_accessible(job_id, upscaled_path_or_url, s3_key_prefix="upscaled")
    orig_ref = _ensure_image_accessible(job_id, original_path_or_url, s3_key_prefix="original")

    combined_user = user_prompt + "\n\n" + \
                    f"Upscaled image: {up_ref}\nOriginal image: {orig_ref}\n\n" \
                    "Answer with exactly one word: 'yes' or 'no'. You may optionally add a one-line reason."

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_user}
            ],
            temperature=0.0,
            max_tokens=48
        )
        # log raw response
        try:
            log_gpt_response(job_id, resp, combined_user, "similarity_gpt_raw")
        except Exception:
            print("[gpt5-check] warning: failed to log response")

        txt = None
        try:
            txt = _extract_text_from_openai_resp(resp)
        except Exception:
            try:
                txt = resp['choices'][0]['message'].get('content', "")
            except Exception:
                txt = None

        if txt:
            tl = txt.strip().lower()
            print("[gpt5-check] extracted text:", tl)
            if tl.startswith("y") or "yes" in tl or "agree" in tl:
                return True
            if tl.startswith("n") or "no" in tl or "not" in tl:
                return False
            # ambiguous -> log and return None
            print("[gpt5-check] ambiguous response:", txt)
            return None
        else:
            print("[gpt5-check] WARNING: no content in GPT response")
            return None
    except Exception as e:
        print(f"[gpt5-check] error: {e}")
        try:
            log_gpt_response(job_id, {"error": str(e)}, combined_user, "similarity_gpt_error")
        except Exception:
            pass
    return None



# def call_gpt5_for_upscale_prompt(system_prompt: str, user_prompt: str, image_urls: List[str]) -> Optional[str]:
#     combined_user = user_prompt + "\n\n" + "\n".join(f"Image {i+1}: {u}" for i, u in enumerate(image_urls))

#     try:
#         resp = openai.ChatCompletion.create(
#             model="gpt-5",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": combined_user}
#             ]
#         )

#         print("[gpt5-upscale] raw response:\n", json.dumps(resp, indent=2))

#         txt = resp['choices'][0]['message'].get('content', "")
#         if txt:
#             txt = txt.strip()
#             print("[gpt5-upscale] extracted text:", txt)
#             return txt
#         else:
#             print("[gpt5-upscale] WARNING: no content in GPT response")
#     except Exception as e:
#         print(f"[gpt5-upscale] error: {e}")

#     return None


# def call_gpt5_for_similarity_check(system_prompt: str, user_prompt: str, upscaled_url: str, original_url: str) -> Optional[bool]:
#     combined_user = (
#         user_prompt + "\n\n" +
#         f"Upscaled image: {upscaled_url}\nOriginal: {original_url}\n\n"
#         "Answer exactly one word: yes or no."
#     )

#     try:
#         resp = openai.ChatCompletion.create(
#             model="gpt-5",
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": combined_user}
#             ]
#         )

#         print("[gpt5-check] raw response:\n", json.dumps(resp, indent=2))

#         txt = resp['choices'][0]['message'].get('content', "")
#         if txt:
#             txt = txt.strip().lower()
#             print("[gpt5-check] extracted text:", txt)

#             if txt.startswith("y") or "yes" in txt:
#                 return True
#             if txt.startswith("n") or "no" in txt:
#                 return False
#         else:
#             print("[gpt5-check] WARNING: no content in GPT response")
#     except Exception as e:
#         print(f"[gpt5-check] error: {e}")

#     return None

# ---------- Prompt helpers ----------
def _http_image_or_none(url: str) -> Optional[str]:
    u = (url or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else None

from style_presets import SCENE_SETTINGS, SCENE_DETAIL, PRESENTER_STYLES, PRESENTER_DETAIL
from chunker import split_script
from models import JobStatus
from veo_pollo_client import PolloClient

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
        prefix = f"Open directly inside a {scene['env']}. Presenter ({persona['persona']}) is holding the {product}. "
    else:
        prefix = f"{brand} {product} promo. {persona['persona']} in a {scene['env']}. "
    base = (
        f"{prefix}"
        f"{static_rules}"
        f"Lighting: {scene['lighting']}. "
        f"Presenter faces camera and presenter's body must be visible till knees and clearly says: \"{text}\" "
        f"Presenter's skin must be clear, {persona['skin']}."
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

    # Keep the path/url for the first chunk 10th frame
    first_chunk_10th_path: Optional[str] = None
    first_chunk_10th_s3_url: Optional[str] = None

    # Keep previous chunk's best tail for continuity
    previous_best_png_path: Optional[str] = None
    previous_best_png_s3_url: Optional[str] = None

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

            # Save first chunk's 10th frame path & upload to S3 (only once)
            if i == 1:
                tenth_path = frame_path(frames_dir, 10)
                if os.path.exists(tenth_path):
                    first_chunk_10th_path = tenth_path
                    try:
                        # upload
                        key = f"{S3_PREFIX}/{job_id}/first_chunk_frame_0010.png"
                        first_chunk_10th_s3_url = upload_public_png(first_chunk_10th_path, key)
                        errors.append(f"INFO: uploaded first-chunk 10th frame -> {first_chunk_10th_s3_url}")
                    except Exception as e:
                        errors.append(f"WARN: failed to upload first-chunk 10th frame: {e}")
                else:
                    errors.append("WARN: first-chunk 10th frame missing")

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

            # ---------- NEW dynamic GPT5 -> Gemini upscaling flow ----------
            try:
                anchor_a_path = first_chunk_10th_path or frame_path(frames_dir, 10)
                anchor_b_path = previous_best_png_path or best_png  # for chunk 1 previous_best_png_path is None, so use current best

                # Upload both images to S3 (so GPT can access URLs)
                a_s3 = first_chunk_10th_s3_url
                if not a_s3:
                    try:
                        key_a = f"{S3_PREFIX}/{job_id}/first_chunk_frame_0010.png"
                        a_s3 = upload_public_png(anchor_a_path, key_a)
                        first_chunk_10th_s3_url = a_s3
                    except Exception as e:
                        errors.append(f"WARN upload A failed: {e}; using local path")
                        a_s3 = None

                try:
                    key_b = f"{S3_PREFIX}/{job_id}/scene_{i:02d}_best_tail.png"
                    b_s3 = upload_public_png(anchor_b_path, key_b)
                    previous_best_png_s3_url = b_s3
                except Exception as e:
                    errors.append(f"WARN upload B failed: {e}")
                    b_s3 = None

                # Prepare GPT system and user prompts (these can be customized/extended as env vars)
                gpt_system_for_prompt = os.getenv("GPT_SYSTEM_PROMPT_UPSCALE",
                    "You are an expert image enhancer prompt generator. Given two reference images, produce a concise, explicit prompt that will instruct an image upscaler to produce a realistic upscale of the second image similar to first image while preserving exact likeness, pose, clothing and context. Avoid adding new objects. Keep the prompt limited to actionable, model-friendly instructions.")
                gpt_user_for_prompt = os.getenv("GPT_USER_PROMPT_UPSCALE",
                    "Produce a single short but complete prompt for an image upscaler. Inputs:\n"
                    " - Reference image A (anchor, high-quality framing): {A}\n"
                    " - Target image B (to be upscaled): {B}\n"
                    "Output should be a single paragraph, optimized for photorealistic upscaling, mention preservation of identity and no new elements. Do not output anything else.")

                # Fill in image placeholders for user prompt (GPT will also receive raw URLs appended in our helper)
                filled_user_prompt = gpt_user_for_prompt.replace("{A}", a_s3 or anchor_a_path).replace("{B}", b_s3 or anchor_b_path)

                # Call gpt-5 to generate the gemini prompt
                gemini_prompt_text = None
                gemini_prompt_text = call_gpt5_for_upscale_prompt(job_id, gpt_system_for_prompt, filled_user_prompt, [a_s3 or anchor_a_path, b_s3 or anchor_b_path])

                if not gemini_prompt_text:
                    errors.append(f"WARN scene {i}: gpt-5 did not return a prompt; falling back to default GEMINI prompt")
                    gemini_prompt_text = os.getenv("GEMINI_UPSCALE_PROMPT", """Enhance this image to 4K resolution. Improve clarity and sharpness in all blurred areas (especially the face, eyes, and hands) while keeping the subject’s exact likeness, pose, clothing, and background unchanged. Maintain natural colors, lighting, and framing. Avoid adding new elements, artifacts, or stylization. The result should look photorealistic, clean, and naturally sharp.""")

                # Attempt gemini upscales (with retries)
                upscaled_path = os.path.join(out_dir, f"scene_{i:02d}_cont_gemini_upscaled.png")
                upscale_ok = False
                last_upscaled_s3_url = None
                for attempt in range(1, MAX_GEMINI_RETRIES + 1):
                    print(f"[upscale] scene {i} attempt {attempt} with prompt len {len(gemini_prompt_text or '')}")
                    if gemini_upscale_image(anchor_b_path, upscaled_path, gemini_prompt_text):
                        # Upload upscaled to S3
                        try:
                            key_up = f"{S3_PREFIX}/{job_id}/scene_{i:02d}_cont_upscaled.png"
                            last_upscaled_s3_url = upload_public_png(upscaled_path, key_up)
                        except Exception as e:
                            errors.append(f"WARN: upload of upscaled failed: {e}")
                            last_upscaled_s3_url = None

                        # Now ask gpt-5 whether upscaled image is similar enough to original (B)
                        gpt_system_for_check = os.getenv("GPT_SYSTEM_PROMPT_CHECK",
                            "You are a visual quality analyst. You will be given two images: an upscaled image and an original (non-upscaled) reference. Answer 'yes' if the upscaled version preserves the identity, pose, clothing, and visual fidelity of the original and could be used as a continuity reference; answer 'no' otherwise.")
                        gpt_user_for_check = os.getenv("GPT_USER_PROMPT_CHECK",
                            "Compare the upscaled image to the original. Provide only a single-word answer: 'yes' or 'no'.")

                        similarity = call_gpt5_for_similarity_check(job_id, gpt_system_for_check, gpt_user_for_check, last_upscaled_s3_url or upscaled_path, b_s3 or anchor_b_path)
                        if similarity is True:
                            upscale_ok = True
                            errors.append(f"INFO scene {i}: upscaled accepted by gpt-5 on attempt {attempt}")
                            break
                        elif similarity is False:
                            errors.append(f"INFO scene {i}: upscaled rejected by gpt-5 on attempt {attempt}; retrying")
                            # optionally modify prompt or wait; here we retry same prompt (could be enhanced to request a new prompt)
                        else:
                            errors.append(f"WARN scene {i}: similarity check inconclusive on attempt {attempt}; retrying")
                    else:
                        errors.append(f"WARN scene {i}: gemini failed to produce image on attempt {attempt}")
                    time.sleep(1 + attempt)

                # Decide used_path (what to use as continuity image for next chunk)
                if upscale_ok and last_upscaled_s3_url:
                    used_path = upscaled_path
                    used_s3_url = last_upscaled_s3_url
                else:
                    # fallback to non-upscaled best_png
                    used_path = anchor_b_path
                    used_s3_url = b_s3 or (previous_best_png_s3_url if previous_best_png_s3_url else None)
                    errors.append(f"WARN scene {i}: using non-upscaled best frame as continuity due to unsuccessful upscale/validation")

                # set next_image_url for next chunk
                next_image_url = used_s3_url or _http_image_or_none(used_path) or None
                errors.append(f"INFO scene {i}: continuity frame -> {next_image_url}")

                # Save previous best for next chunk continuity
                previous_best_png_path = best_png
                if not previous_best_png_s3_url:
                    try:
                        previous_best_png_s3_url = upload_public_png(best_png, f"{S3_PREFIX}/{job_id}/scene_{i:02d}_best_tail_static.png")
                    except Exception:
                        previous_best_png_s3_url = None

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
