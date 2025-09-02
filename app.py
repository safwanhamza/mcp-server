# app.py
import os, json, time, threading, queue
from collections import deque
from fractions import Fraction
from typing import Optional

import numpy as np
from flask import Flask, Response, request, send_from_directory, jsonify
from flask_sock import Sock
import soundfile as sf

# High-quality resampler + VAD
try:
    from scipy.signal import resample_poly  # polyphase, anti-aliased
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

import webrtcvad  # WebRTC Voice Activity Detector (fast, robust)

import torch
import nemo.collections.asr as nemo_asr
from omegaconf import open_dict

###############################################################################
# Config
###############################################################################
MODEL_ID = "nvidia/parakeet-tdt-0.6b-v3"

# ASR expects mono/16 kHz
ASR_SR = 16000

# Sliding window + decode cadence
WINDOW_SECONDS = 8.0
STEP_SECONDS = 0.8
FINAL_UPDATE_SECONDS = 3.0
MAX_BUFFER_SECONDS = 90.0

# VAD settings (WebRTC VAD supports 10/20/30 ms frames at 8/16/32/48 kHz)
VAD_MODE = 2        # 0=least aggressive, 3=most
VAD_FRAME_MS = 20   # ms
VAD_HANGOVER_MS = 300  # keep last few frames after speech to avoid choppiness

###############################################################################
# Model load
###############################################################################
device = "cuda" if torch.cuda.is_available() else "cpu"
asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODEL_ID).to(device)

decoding_cfg = asr_model.cfg.decoding
with open_dict(decoding_cfg):
    decoding_cfg.strategy = "greedy_batch"
asr_model.change_decoding_strategy(decoding_cfg)

pre_cfg = asr_model.cfg.preprocessor
with open_dict(pre_cfg):
    pre_cfg.dither = 0.0
    pre_cfg.pad_to = 0

###############################################################################
# Buffers and helpers
###############################################################################
class Ring:
    def __init__(self, sr=ASR_SR, max_seconds=MAX_BUFFER_SECONDS):
        self.sr = sr
        self.buf = deque(maxlen=int(max_seconds * sr))
        self.session = []   # full session (voiced audio only)

    def extend(self, x: np.ndarray):
        self.buf.extend(x)
        self.session.append(x)

    def latest_window(self, seconds: float) -> Optional[np.ndarray]:
        n = int(seconds * self.sr)
        if len(self.buf) < int(0.5 * self.sr):
            return None
        a = np.array(self.buf, dtype=np.float32)
        return a if len(a) <= n else a[-n:]

    def session_audio(self) -> Optional[np.ndarray]:
        if not self.session:
            return None
        return np.concatenate(self.session).astype(np.float32)

ring = Ring()

def to_int16(x: np.ndarray) -> np.ndarray:
    y = np.clip(x, -1.0, 1.0)
    return (y * 32767.0).astype(np.int16)

def normalize(x: np.ndarray, target_rms=0.06, max_gain=12.0) -> np.ndarray:
    if x.size == 0:
        return x
    r = float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))
    if r < 1e-7:
        return x
    g = min(target_rms / r, max_gain)
    return np.clip(x * g, -1.0, 1.0).astype(np.float32)

def resample_high_quality(x: np.ndarray, in_sr: int, out_sr: int) -> np.ndarray:
    if in_sr == out_sr:
        return x.astype(np.float32)
    if HAVE_SCIPY:
        # Polyphase resampling (anti-aliased, zero-phase FIR)
        frac = Fraction(in_sr, out_sr).limit_denominator()
        up, down = frac.denominator, frac.numerator  # because in_sr/out_sr = up/down
        # We want y at out_sr; resample_poly expects up/down relative to x.
        # If in_sr=48000 → out_sr=16000, in_sr/out_sr=3 ⇒ up=1, down=3 (handled below)
        # So compute directly:
        g = Fraction(out_sr, in_sr).limit_denominator()
        up, down = g.numerator, g.denominator
        y = resample_poly(x, up, down).astype(np.float32)
        return y
    # Fallback: linear (not ideal but better than nothing)
    n_out = int(round(len(x) * out_sr / in_sr))
    return np.interp(np.linspace(0, len(x), n_out, endpoint=False),
                     np.arange(len(x)), x).astype(np.float32)

###############################################################################
# SSE (for live text to browser)
###############################################################################
listeners = set()
listeners_lock = threading.Lock()

def register_listener():
    q = queue.Queue()
    with listeners_lock:
        listeners.add(q)
    return q

def remove_listener(q):
    with listeners_lock:
        listeners.discard(q)

def publish(partial=None, final=None, status=None):
    payload = {"ts": time.time()}
    if partial is not None: payload["partial"] = partial
    if final   is not None: payload["final"]   = final
    if status  is not None: payload["status"]  = status
    msg = json.dumps(payload)
    with listeners_lock:
        for q in list(listeners):
            try:
                q.put_nowait(msg)
            except Exception:
                try: listeners.remove(q)
                except KeyError: pass

###############################################################################
# Decoder thread
###############################################################################
run_flag = threading.Event()
final_text = ""

def transcribe_array(audio_f32_mono: np.ndarray, sr=ASR_SR) -> str:
    import tempfile
    if audio_f32_mono is None or len(audio_f32_mono) < sr * 0.5:
        return ""
    audio_f32_mono = normalize(audio_f32_mono)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    sf.write(tmp, audio_f32_mono, sr, subtype="PCM_16")
    try:
        try:
            hyp = asr_model.transcribe([tmp], batch_size=1, return_hypotheses=True)
            return hyp[0].text if hyp and hasattr(hyp[0], "text") else (hyp[0] if hyp else "")
        except TypeError:
            hyp = asr_model.transcribe([tmp], batch_size=1)
            return hyp[0] if hyp else ""
    finally:
        try: os.remove(tmp)
        except Exception: pass

def worker_loop():
    global final_text
    last_p = last_f = 0.0
    latest_text = ""
    while run_flag.is_set():
        now = time.time()
        wnd = ring.latest_window(WINDOW_SECONDS)
        if wnd is not None and (now - last_p) >= STEP_SECONDS:
            text = transcribe_array(wnd, ASR_SR)
            if text:
                latest_text = text
                publish(partial=latest_text, final=final_text)
            last_p = now
        if (now - last_f) >= FINAL_UPDATE_SECONDS:
            sess = ring.session_audio()
            if sess is not None and len(sess) > ASR_SR * 1.0:
                final_text = transcribe_array(sess, ASR_SR)
                publish(partial=latest_text, final=final_text)
            last_f = now
        time.sleep(0.03)

###############################################################################
# Flask + WebSocket
###############################################################################
app = Flask(__name__, static_folder="static", static_url_path="/static")
sock = Sock(app)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/events")
def sse():
    def stream(q):
        try:
            yield ":ok\n\n"
            while True:
                yield f"data: {q.get()}\n\n"
        finally:
            remove_listener(q)
    q = register_listener()
    return Response(stream(q), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache","X-Accel-Buffering": "no"})

@app.route("/start", methods=["POST"])
def start():
    if run_flag.is_set():
        return jsonify({"ok": True, "status": "already_running"})
    # reset buffers
    ring.buf.clear()
    ring.session.clear()
    run_flag.set()
    threading.Thread(target=worker_loop, daemon=True).start()
    publish(status="started", partial="", final="")
    return jsonify({"ok": True, "status": "started"})

@app.route("/stop", methods=["POST"])
def stop():
    global final_text
    if not run_flag.is_set():
        return jsonify({"ok": True, "status": "already_stopped", "final": final_text})
    run_flag.clear()
    sess = ring.session_audio()
    if sess is not None and len(sess) > ASR_SR * 0.5:
        final_text = transcribe_array(sess, ASR_SR)
        publish(final=final_text)
    publish(status="stopped")
    return jsonify({"ok": True, "status": "stopped", "final": final_text})

@sock.route("/ws")
def ws(ws):
    """
    Browser sends:
      1) Text JSON: {"op":"hello","sampleRate": <number>}
      2) Then binary frames: Float32Array PCM at that sampleRate (usually 48000)
    We resample → 16k, gate with WebRTC VAD, and append voiced audio to buffers.
    """
    vad = webrtcvad.Vad(VAD_MODE)
    in_sr = 48000  # default until we get hello
    hang = 0
    voiced_any = False

    # Buffer for accumulating exactly 20ms at 16k (320 samples)
    acc_16k = np.zeros(0, dtype=np.float32)
    frame_16k = int(ASR_SR * VAD_FRAME_MS / 1000.0)  # 320

    publish(status="mic_connected")

    while True:
        msg = ws.receive()
        if msg is None:
            break
        if isinstance(msg, str):
            try:
                meta = json.loads(msg)
                if meta.get("op") == "hello" and "sampleRate" in meta:
                    in_sr = int(meta["sampleRate"])
            except Exception:
                pass
            continue

        # Binary: Float32 PCM from browser
        f32 = np.frombuffer(msg, dtype=np.float32)
        if f32.size == 0:
            continue

        # High-quality resample to 16 kHz (polyphase if SciPy available)
        y = resample_high_quality(f32, in_sr, ASR_SR)

        # Accumulate and run VAD on 20ms frames
        acc_16k = np.concatenate([acc_16k, y])
        while len(acc_16k) >= frame_16k:
            chunk = acc_16k[:frame_16k]
            acc_16k = acc_16k[frame_16k:]
            pcm16 = to_int16(chunk).tobytes()
            is_voice = vad.is_speech(pcm16, ASR_SR)
            if is_voice:
                ring.extend(chunk)
                voiced_any = True
                hang = int(VAD_HANGOVER_MS / VAD_FRAME_MS)
            elif hang > 0:
                # keep a little tail so words aren't chopped
                ring.extend(chunk)
                hang -= 1

    # If connection drops mid-utterance, do a last update
    if voiced_any:
        sess = ring.session_audio()
        if sess is not None and len(sess) > ASR_SR * 0.5:
            text = transcribe_array(sess, ASR_SR)
            publish(final=text)

if __name__ == "__main__":
    # Requirements: pip install flask flask-sock simple-websocket scipy webrtcvad soundfile nemo_toolkit[asr]
    app.run(host="127.0.0.1", port=7862, threaded=True)
