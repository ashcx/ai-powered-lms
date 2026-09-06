import sys, os

# If this script is run directly, remove its directory from sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
if sys.path and sys.path[0] == _script_dir:
    sys.path.pop(0)

import os, tempfile, uuid, argparse, openai, re, shlex, json, platform, subprocess, sys, random
import ffmpeg
from pathlib import Path
from typing import Union
from dotenv import load_dotenv
from tqdm import tqdm

FORMAT = "mp3"

load_dotenv()
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")

# openai tts 
def tts_generate(text: str, voice: str = "alloy", speed: float = 1.25) -> Path:
    client = openai.OpenAI()
    tmp_path = Path(tempfile.gettempdir()) / f"tts_{uuid.uuid4().hex}.{FORMAT}"

    with open(tmp_path, "wb") as f:
        resp= client.audio.speech.create(
            model="gpt-4o-mini-tts",  # fastest public model
            voice=voice,
            input=text,
            response_format=FORMAT,
            speed=speed,
        ) 
        for chunk in resp.iter_bytes():
            f.write(chunk)  

    return tmp_path

# generate video
def create_brainrot_video(
    text: str,
    video_path: Union[str, Path] = Path(__file__).parent.resolve() / "source_brainrot.mp4",
    output_path: Union[str, Path] = Path(__file__).parent.resolve() / "output_brainrot.mp4",
    voice: str = "nova",
    tts_speed: float = 1.15,
    font_size_ratio: float = 0.035,
):

    video_path = Path(video_path)
    output_path = Path(output_path)
    # Absolute path to the font file
    font_file = str(Path(__file__).parent / "Raleway-ExtraBold.ttf")
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    # 1. Generate audio (TTS)
    tqdm.write("[1/3] Generating narration (OpenAI TTS – this may take a few seconds)…")
    audio_tmp = tts_generate(text, voice=voice, speed=tts_speed)

    tqdm.write("[2/3] Transcribing TTS audio (OpenAI Whisper – this may take a few seconds)…")
    # 1b. Transcribe the generated TTS audio to obtain accurate timestamps
    client = openai.OpenAI()
    with open(audio_tmp, "rb") as af:
        whisper_resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=af,
            response_format="verbose_json",
            timestamp_granularities=["segment", "word"]  # request both segment‑ and word‑level timings
        )
    # TranscriptionVerbose is a Pydantic model; use its attribute directly.

    segments = whisper_resp.segments  # list of Segment objects
    if segments is None:
        # Build pseudo‑segments by grouping words (4 words each) so we still get timing pairs.
        words = whisper_resp.words or []
        if not words:
            raise RuntimeError("Whisper returned neither segments nor words; cannot build captions.")
        group_size = 4
        segments = []
        for i in range(0, len(words), group_size):
            batch = words[i:i+group_size]
            start = batch[0].start
            end = batch[-1].end
            text = " ".join(w.word for w in batch)
            # Mimic the Segment dataclass with a simple namespace
            segments.append(type("Seg", (), {"start": start, "end": end, "text": text}))

    # Get audio duration via ffprobe
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_tmp)],
        capture_output=True, text=True, check=True
    )
    audio_duration = float(result.stdout.strip())

    # Get video duration via ffprobe
    vprobe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, check=True
    )
    video_duration = float(vprobe.stdout.strip())

    # Compute slack between video and audio
    diffSecs = max(0.0, video_duration - audio_duration)

    # Choose a safe random start so the audio can fully play before the video ends
    # Need some breathing room: at least 2s head + 5s tail suggested
    start_sec = 0.0
    if diffSecs > 7.0:
        low = 2
        high = int(diffSecs - 5)
        if high > low:
            start_sec = float(random.randint(low, high))

    # Clamp to ensure audio fits (start + audio_duration <= video_duration)
    max_start = max(0.0, video_duration - audio_duration)
    if start_sec > max_start:
        start_sec = max_start

    if video_duration < audio_duration:
        tqdm.write("[warn] Audio is longer than the video; output will end when the shortest stream finishes (-shortest).")

    tqdm.write(f"[seek] Video={video_duration:.3f}s, Audio={audio_duration:.3f}s, diffSecs={diffSecs:.3f}s, start={start_sec:.3f}s")

    # Build caption chunks: 4‑5‑word phrases respecting punctuation
    chunks, timestamps = [], []

    punct_pat = re.compile(r'([\.\\,\!\?\;\:])')

    for seg in segments:
        raw = seg.text.strip()
        if not raw:
            continue

        # 1) split by punctuation, keep delimiter attached to preceding part
        parts = []
        tokens = punct_pat.split(raw)
        for i in range(0, len(tokens), 2):
            unit = tokens[i].strip()
            if not unit:
                continue
            if i + 1 < len(tokens):
                unit += tokens[i + 1]  # append punctuation
            parts.append(unit)

        # 2) further break each piece into 4‑5‑word groups
        seg_duration = seg.end - seg.start
        seg_words = sum(len(p.split()) for p in parts) or 1  # avoid div/0

        for part in parts:
            words = part.split()
            if not words:
                continue
            group_size = 5
            num_groups = (len(words) + group_size - 1) // group_size
            for g_idx in range(num_groups):
                sub_words = words[g_idx*group_size:(g_idx+1)*group_size]
                phrase = " ".join(sub_words)

                # linear interpolation for timing
                word_pos_start = sum(len(p.split()) for p in parts[:parts.index(part)]) + g_idx*group_size
                word_pos_end   = word_pos_start + len(sub_words)
                frac_start = word_pos_start / seg_words
                frac_end   = word_pos_end   / seg_words

                start_t = seg.start + frac_start * seg_duration
                end_t   = seg.start + frac_end   * seg_duration

                chunks.append(phrase)
                timestamps.append((start_t, end_t))

    print(chunks)
    print(timestamps)

    ## encoder tests for windows
    def _run(cmd: list[str], timeout: int = 5) -> bool:
        """Return True if the ffmpeg command exits 0, else False."""
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=timeout)
            return p.returncode == 0
        except Exception:
                return False

    def _probe_nvenc() -> bool:
        # Safe 1-frame test; NVENC likes yuv420p input
        return _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=1",
            "-frames:v", "1", "-vf", "format=yuv420p",
            "-an", "-c:v", "h264_nvenc", "-f", "null", "-"
        ])

    def _probe_qsv() -> bool:
        # QSV requires a QSV device + NV12 upload to GPU
        return _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-init_hw_device", "qsv=hw", "-filter_hw_device", "hw",
            "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=1",
            "-frames:v", "1",
            "-vf", "format=nv12,hwupload=extra_hw_frames=8",
            "-an", "-c:v", "h264_qsv", "-f", "null", "-"
        ])

    def _probe_amf() -> bool:
        # AMF works with yuv420p/NV12; keep it simple
        return _run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=1",
            "-frames:v", "1", "-pix_fmt", "yuv420p",
            "-an", "-c:v", "h264_amf", "-f", "null", "-"
        ])

    # Determine best available hardware encoder
    try:
        encoders_text = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        tqdm.write(f"Error: {e}")
        tqdm.write("Possibly the system has no ffmpeg installed, or not added to PATH. ")
        encoders_text = ""
        sys.exit(0)

    video_codec: str | None = None
    ffmpeg_opts: list[str] | None = None

    if platform.system() == "Darwin":
        if "h264_videotoolbox" in encoders_text:
            video_codec = "h264_videotoolbox"
            ffmpeg_opts = ["-crf", "26"]  # constant-quality for VT
        else:
            video_codec = "libx264"
            ffmpeg_opts = ["-crf", "26", "-preset", "ultrafast"]

    elif platform.system() == "Windows":
        if os.cpu_count() >= 32:
            video_codec = "libx264"
            ffmpeg_opts = ["-crf", "26", "-preset", "ultrafast"]
        elif _probe_qsv():
            video_codec = "h264_qsv"
            ffmpeg_opts = ["-rc", "icq", "-global_quality", "26", "-preset", "7", "-look_ahead", "1"]
        elif _probe_nvenc():
            video_codec = "h264_nvenc"
            ffmpeg_opts = ["-rc", "vbr", "-cq", "26", "-preset", "p2"]  # (optional: "-b:v","0")
        elif _probe_amf():
            video_codec = "h264_amf"
            ffmpeg_opts = ["-rc", "cqp", "-qp_i", "26", "-qp_p", "26", "-usage", "ultralowlatency"]
        else:
            video_codec = "libx264"
            ffmpeg_opts = ["-crf", "26", "-preset", "ultrafast"]

    else: 
        if "h264_nvenc" in encoders_text:
            video_codec = "h264_nvenc"
            ffmpeg_opts = ["-cq", "26", "-preset", "p2"]
        elif "h264_qsv" in encoders_text:
            video_codec = "h264_qsv"
            ffmpeg_opts = ["-global_quality", "26", "-preset", "veryfast"]
        else:
            video_codec = "libx264"
            ffmpeg_opts = ["-crf", "26", "-preset", "ultrafast"]

    tqdm.write(f"[3/3] Encoding video with FFmpeg:\nSelected video encoder: {video_codec}")

    # Build and run ffmpeg command
    video_in  = ffmpeg.input(str(video_path), ss=start_sec, t=audio_duration)
    audio_in  = ffmpeg.input(str(audio_tmp))

    # base video: scale to 1280p
    v = video_in.filter("scale", "-2", "1280")

    font_path = str(font_file)              # absolute path string
    base_fs   = int(font_size_ratio * 1280) # cached fontsize

    for phrase, (start_t, end_t) in zip(chunks, timestamps):
        # Soft‑wrap: balance words over two lines (max ~30 chars each)
        if len(phrase) > 30:
            midpoint = len(phrase) // 2
            # find nearest space to midpoint (look left, then right)
            left_space  = phrase.rfind(" ", 0, midpoint)
            right_space = phrase.find(" ", midpoint)
            if left_space == -1 and right_space == -1:
                split_idx = midpoint
            else:
                # choose the closer space
                if left_space == -1:
                    split_idx = right_space
                elif right_space == -1:
                    split_idx = left_space
                else:
                    split_idx = left_space if (midpoint - left_space) <= (right_space - midpoint) else right_space

            line1 = phrase[:split_idx].strip()
            line2 = phrase[split_idx + 1 :].strip()
        else:
            line1, line2 = phrase, None

        if line2 is None:
            # single line
            v = v.drawtext(
                fontfile=font_path,
                text=line1,
                fontsize=base_fs,
                fontcolor="white",
                borderw=4,
                bordercolor="black",
                x="(w-text_w)/2",
                y="(h*0.7)",
                enable=f"between(t,{start_t},{end_t})",
            )
        else:
            # two centred lines: first above, second below reference y
            v = v.drawtext(
                fontfile=font_path,
                text=line1,
                fontsize=base_fs,
                fontcolor="white",
                borderw=4,
                bordercolor="black",
                x="(w-text_w)/2",
                y="(h*0.7-text_h/3*2)",
                enable=f"between(t,{start_t},{end_t})",
            ).drawtext(
                fontfile=font_path,
                text=line2,
                fontsize=base_fs,
                fontcolor="white",
                borderw=4,
                bordercolor="black",
                x="(w-text_w)/2",
                y="(h*0.7+text_h/3*2)",
                enable=f"between(t,{start_t},{end_t})",
            )

    # output with chosen encoder params
    out = ffmpeg.output(
        v, audio_in,
        str(output_path),
        vcodec=video_codec,
        pix_fmt="yuv420p",
        acodec="aac",
        shortest=None,
        threads=str(os.cpu_count() or 1),
    )

    out.global_args(*ffmpeg_opts)

    # run ffmpeg; raise if non‑zero
    try:
        # Run ffmpeg and let it emit stderr directly to console/logs
        ffmpeg.run(out, overwrite_output=True)
    except ffmpeg.Error as e:
        # If ffmpeg.Error contains stderr, print it explicitly
        if hasattr(e, "stderr") and e.stderr:
            sys.stderr.write("FFmpeg stderr:\n")
            sys.stderr.write(e.stderr.decode("utf-8"))
        raise

    # Clean up audio temp
    try: audio_tmp.unlink()
    except OSError: pass

    tqdm.write(f"✅ Done! Saved to {output_path}")

if __name__ == "__main__":
    text = '''Self-attention, sometimes called intra-attention is an attention mechanism relating different positions
    of a single sequence in order to compute a representation of the sequence. Self-attention has been
    used successfully in a variety of tasks including reading comprehension, abstractive summarization,
    textual entailment and learning task-independent sentence representations [4, 27, 28, 22].
    End-to-end memory networks are based on a recurrent attention mechanism instead of sequencealigned recurrence and have been shown to perform well on simple-language question answering and
    language modeling tasks [34].
    To the best of our knowledge, however, the Transformer is the first transduction model relying
    entirely on self-attention to compute representations of its input and output without using sequencealigned RNNs or convolution. In the following sections, we will describe the Transformer, motivate
    self-attention and discuss its advantages over models such as [17, 18] and [9].'''
    create_brainrot_video(text)