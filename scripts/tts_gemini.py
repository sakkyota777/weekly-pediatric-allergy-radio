#!/usr/bin/env python3
"""Generate an MP3 narration from a Japanese radio script using Gemini TTS.

Usage:
    python scripts/tts_gemini.py <script.txt> <out.mp3> [--voice Kore]

The script text is chunked (by blank-line separated blocks, further split so
each request stays well under the model limit), each chunk is synthesised with
the Gemini `*-tts` model, the returned raw PCM (L16, 24kHz, mono) chunks are
concatenated into a single WAV, and finally encoded to MP3 with the ffmpeg
binary bundled by `imageio-ffmpeg` (no system ffmpeg required).

Requires the environment variable GEMINI_API_KEY (Google AI Studio key).
Exits non-zero with a clear message if the key is missing so the weekly
pipeline can fall back to a text/infographic-only deliverable.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import subprocess
import sys
import time
import wave

import requests

# 24kHz mono 16-bit little-endian PCM is what the Gemini TTS models return.
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (16-bit)

MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
DEFAULT_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Kore")
# libmp3lame VBR quality: lower is better quality and a bigger file. A weekly
# 8-10 minute episode has to stay under Notion's 5 MiB free-workspace limit,
# so trade a little fidelity for headroom. Override with GEMINI_TTS_QSCALE.
QSCALE = os.environ.get("GEMINI_TTS_QSCALE", "4")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

# Keep each synthesis request modest; the model has a per-request token budget
# and shorter chunks are more reliable. Chunks are split on blank lines first,
# then greedily packed up to this character budget.
CHUNK_CHAR_BUDGET = 1200
MAX_RETRIES = 4


def die(msg: str, code: int = 1) -> None:
    print(f"[tts_gemini] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def chunk_script(text: str) -> list[str]:
    """Split the script into synthesis-sized chunks, preserving paragraph order."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        # A single oversized block is split on sentence-ish boundaries.
        if len(block) > CHUNK_CHAR_BUDGET:
            if current:
                chunks.append(current)
                current = ""
            piece = ""
            for sentence in _split_sentences(block):
                if len(piece) + len(sentence) > CHUNK_CHAR_BUDGET and piece:
                    chunks.append(piece)
                    piece = ""
                piece += sentence
            if piece:
                chunks.append(piece)
            continue
        if len(current) + len(block) + 2 > CHUNK_CHAR_BUDGET and current:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)
    return chunks


def _split_sentences(block: str) -> list[str]:
    out: list[str] = []
    buf = ""
    for ch in block:
        buf += ch
        if ch in "。．.!?！？\n":
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def build_speech_config(voice: str, speakers: list[tuple[str, str]] | None) -> dict:
    """Single- or multi-speaker speechConfig for the Gemini TTS request.

    When `speakers` (a list of (name, voice) pairs, max 2) is given, a
    multiSpeakerVoiceConfig is built so each labelled speaker in the script
    gets its own voice. Otherwise a single prebuilt voice is used.
    """
    if speakers:
        return {
            "multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": [
                    {"speaker": name,
                     "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}}
                    for name, v in speakers
                ]
            }
        }
    return {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}


def synthesize_chunk(text: str, api_key: str, speech_config: dict,
                     speakers: list[tuple[str, str]] | None) -> bytes:
    """Return raw PCM bytes for one chunk from the Gemini TTS API."""
    url = f"{API_ROOT}/models/{MODEL}:generateContent"
    if speakers:
        # A short instruction line frames the chunk as a conversation and is
        # interpreted as a style directive (not read aloud). It also keeps each
        # chunk self-describing when the script is split across requests.
        names = "と".join(name for name, _ in speakers)
        prompt = f"次の{names}による会話を、親しみやすいラジオ番組の口調で読み上げてください:\n{text}"
    else:
        prompt = text
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": speech_config,
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                part = data["candidates"][0]["content"]["parts"][0]
                b64 = part["inlineData"]["data"]
                return base64.b64decode(b64)
            # 429/5xx: back off and retry; other 4xx: fail fast with body.
            if resp.status_code in (429, 500, 503):
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            else:
                die(f"Gemini TTS request failed HTTP {resp.status_code}: {resp.text[:500]}")
        except requests.RequestException as exc:  # network-level
            last_err = str(exc)
        sleep_s = 2 ** (attempt + 1)
        print(f"[tts_gemini] retry {attempt + 1}/{MAX_RETRIES} after {sleep_s}s ({last_err})",
              file=sys.stderr)
        time.sleep(sleep_s)
    die(f"Gemini TTS failed after {MAX_RETRIES} retries: {last_err}")
    return b""  # unreachable


def pcm_to_wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_mp3(wav_bytes: bytes, out_path: str) -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", "pipe:0", "-codec:a", "libmp3lame", "-qscale:a", QSCALE, out_path],
        input=wav_bytes,
        capture_output=True,
    )
    if proc.returncode != 0:
        die(f"ffmpeg mp3 encode failed: {proc.stderr.decode('utf-8', 'ignore')[:500]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini TTS -> MP3")
    ap.add_argument("script", help="path to the plain-text radio script")
    ap.add_argument("out", help="output .mp3 path")
    ap.add_argument("--voice", default=DEFAULT_VOICE, help=f"voice name (default {DEFAULT_VOICE})")
    ap.add_argument(
        "--speakers", default=os.environ.get("GEMINI_TTS_SPEAKERS"),
        help="two-speaker mode: 'Name1=Voice1,Name2=Voice2'. The names must match "
             "the 'Name:' labels used in the script. Falls back to single --voice "
             "when omitted.")
    args = ap.parse_args()

    speakers: list[tuple[str, str]] | None = None
    if args.speakers:
        speakers = []
        for pair in args.speakers.split(","):
            if "=" not in pair:
                die(f"--speakers entry '{pair}' must be Name=Voice")
            name, v = pair.split("=", 1)
            speakers.append((name.strip(), v.strip()))
        if not 1 <= len(speakers) <= 2:
            die("--speakers supports 1 or 2 speakers (Gemini TTS limit)")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        die("GEMINI_API_KEY is not set. Set it in the environment to enable audio "
            "generation. (The weekly pipeline will fall back to a text/infographic "
            "deliverable when this is missing.)", code=2)

    with open(args.script, "r", encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text:
        die("script file is empty")

    speech_config = build_speech_config(args.voice, speakers)
    chunks = chunk_script(text)
    if speakers:
        voices_desc = ", ".join(f"{n}={v}" for n, v in speakers)
        print(f"[tts_gemini] synthesising {len(chunks)} chunk(s) with {MODEL} / "
              f"multi-speaker ({voices_desc})")
    else:
        print(f"[tts_gemini] synthesising {len(chunks)} chunk(s) with {MODEL} / voice={args.voice}")
    pcm = bytearray()
    for i, chunk in enumerate(chunks, 1):
        print(f"[tts_gemini]  chunk {i}/{len(chunks)} ({len(chunk)} chars)")
        pcm.extend(synthesize_chunk(chunk, api_key, speech_config, speakers))
        time.sleep(1)  # gentle pacing between requests

    wav_bytes = pcm_to_wav_bytes(bytes(pcm))
    wav_to_mp3(wav_bytes, args.out)
    secs = len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
    print(f"[tts_gemini] wrote {args.out} (~{secs:.0f}s of audio)")


if __name__ == "__main__":
    main()
