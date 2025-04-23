import os
import sys
import struct
import tempfile
import subprocess
import math
from tkinter import filedialog, Tk
from PIL import Image, UnidentifiedImageError
from moviepy import VideoFileClip

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MP4_FILENAME = "output_vid_audio_lossless_mp4.mp4"
DEFAULT_DECRYPTED_FILENAME = "output.bin"
SIZE_HEADER_FORMAT = "!Q"  # 8-byte unsigned long long
SIZE_HEADER_BYTES = struct.calcsize(SIZE_HEADER_FORMAT)

# --- Audio Configuration ---
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
AUDIO_SAMPLE_FORMAT = "s16le"
AUDIO_BYTES_PER_SAMPLE = 2
AUDIO_FRAME_SIZE = AUDIO_BYTES_PER_SAMPLE * AUDIO_CHANNELS  # e.g., 4 bytes per frame
AUDIO_CODEC = "flac"

# --- Utility Functions ---

def parse_hex_key(key_str):
    if not key_str:
        return []
    keys = []
    for part in key_str.strip().split():
        try:
            k = int(part, 16)
            if 0 <= k <= 255:
                keys.append(k)
        except ValueError:
            pass
    return keys


def bytes_to_rgb_list(data_bytes, width, height):
    total_pixels = width * height
    expected_bytes = total_pixels * 3
    if len(data_bytes) != expected_bytes:
        raise ValueError(f"Data length mismatch: expected {expected_bytes}, got {len(data_bytes)}.")
    return [tuple(data_bytes[i:i+3]) for i in range(0, expected_bytes, 3)]


def rgb_list_to_bytes(rgb_list):
    ba = bytearray()
    for r, g, b in rgb_list:
        ba.extend((
            max(0, min(255, int(round(r)))), 
            max(0, min(255, int(round(g)))), 
            max(0, min(255, int(round(b))))
        ))
    return bytes(ba)


def cipher(data, keys, encrypting=True):
    if not keys:
        return data
    out = bytearray(len(data))
    key_len = len(keys)
    for i, byte in enumerate(data):
        k = keys[i % key_len]
        out[i] = (byte + k) % 256 if encrypting else (byte - k + 256) % 256
    return bytes(out)


def run_ffmpeg_process(cmd, stdin_data=None):
    stdin_pipe = subprocess.PIPE if stdin_data is not None else None
    process = subprocess.Popen(cmd, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_data, stderr_data = process.communicate(input=stdin_data)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout_data, stderr=stderr_data)
    return stdout_data

# --- Encode MP4 ---
def encode_mp4(input_path, output_filename, width, height, fps=1):
    output_path = os.path.join(SCRIPT_DIR, output_filename)

    # Read input data
    try:
        with open(input_path, 'rb') as f:
            original_data = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    # Prepend size header
    data_with_header = struct.pack(SIZE_HEADER_FORMAT, len(original_data)) + original_data

    # Encrypt
    keys = parse_hex_key(input("Enter space-separated hex key: ").strip())
    encrypted = cipher(data_with_header, keys, encrypting=True)
    E = len(encrypted)

    # Frame and audio sizes
    bytes_per_frame = width * height * 3
    if bytes_per_frame == 0:
        print("Invalid dimensions.")
        return
    audio_bytes_per_second = AUDIO_SAMPLE_RATE * AUDIO_FRAME_SIZE

    # Determine minimum frame count so that combined capacity ≥ E
    frames = 1
    while True:
        video_cap = frames * bytes_per_frame
        duration = frames / fps
        raw_audio_cap = duration * audio_bytes_per_second
        rem = raw_audio_cap % AUDIO_FRAME_SIZE
        audio_cap = int(raw_audio_cap + (AUDIO_FRAME_SIZE - rem) if rem else raw_audio_cap)
        if video_cap + audio_cap >= E:
            break
        frames += 1

    video_cap = frames * bytes_per_frame
    duration = frames / fps
    raw_audio_cap = duration * audio_bytes_per_second
    rem = raw_audio_cap % AUDIO_FRAME_SIZE
    audio_cap = int(raw_audio_cap + (AUDIO_FRAME_SIZE - rem) if rem else raw_audio_cap)

    total_storage = video_cap + audio_cap

    # Split encrypted data proportionally
    v_share = int((video_cap / total_storage) * E)
    v_share = min(v_share, E)
    a_share = E - v_share

    video_part = encrypted[:v_share]
    audio_part = encrypted[v_share:]

    # Pad each to full capacity
    video_data = video_part.ljust(video_cap, b'\x00')
    audio_data = audio_part.ljust(audio_cap, b'\x00')

    # Generate frames
    frames_dir = tempfile.TemporaryDirectory(prefix="frames_")
    try:
        for i in range(frames):
            chunk = video_data[i*bytes_per_frame:(i+1)*bytes_per_frame]
            pixels = bytes_to_rgb_list(chunk, width, height)
            img = Image.new('RGB', (width, height))
            img.putdata(pixels)
            img.save(os.path.join(frames_dir.name, f"frame_{i:06d}.png"), 'PNG')

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frames_dir.name, "frame_%06d.png"),
            "-f", AUDIO_SAMPLE_FORMAT,
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-ac", str(AUDIO_CHANNELS),
            "-i", "-",
            "-c:v", "libx264rgb", "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "rgb24",
            "-c:a", AUDIO_CODEC,
            "-map", "0:v", "-map", "1:a",
            "-shortest",
            output_path
        ]
        run_ffmpeg_process(cmd, stdin_data=audio_data)
        print(f"MP4 created: {output_path}")
    finally:
        frames_dir.cleanup()

# --- Decode MP4 ---
def decode_mp4(input_path, output_filename):
    output_path = os.path.join(SCRIPT_DIR, output_filename)
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    # Extract video bytes
    vid = VideoFileClip(input_path)
    v_bytes = b''.join(
        rgb_list_to_bytes([tuple(p) for p in frame.reshape(-1, 3)])
        for frame in vid.iter_frames()
    )
    vid.close()

    # Extract audio bytes
    cmd_a = [
        "ffmpeg", "-i", input_path,
        "-vn", "-f", AUDIO_SAMPLE_FORMAT,
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", str(AUDIO_CHANNELS),
        "-acodec", "pcm_s16le",
        "-map", "0:a:0", "-"
    ]
    a_bytes = run_ffmpeg_process(cmd_a)

    combined = v_bytes + a_bytes
    keys = parse_hex_key(input("Enter space-separated hex key: ").strip())
    decrypted = cipher(combined, keys, encrypting=False)

    if len(decrypted) < SIZE_HEADER_BYTES:
        print("Decryption error: Header missing.")
        return

    orig_size = struct.unpack(SIZE_HEADER_FORMAT, decrypted[:SIZE_HEADER_BYTES])[0]
    data = decrypted[SIZE_HEADER_BYTES:SIZE_HEADER_BYTES+orig_size]

    with open(output_path, 'wb') as f:
        f.write(data)
    print(f"File written: {output_path}")

# --- UI ---
def display_ui(target):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n-=- Kaleidoscope by Alex Hall (Preview version) -=-\n")
    print(f"Output directory: {SCRIPT_DIR}\nTarget: {target}\n")
    print("1. Select File")
    print("2. Encrypt to MP4")
    print("3. Decrypt MP4")
    print("4. Exit")


def select_file(current):
    root = Tk(); root.withdraw(); root.attributes('-topmost', True)
    path = filedialog.askopenfilename(initialdir=SCRIPT_DIR)
    root.destroy()
    return path if path else current


def main():
    # Ensure FFmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["ffprobe", "-version"], check=True, stdout=subprocess.DEVNULL)
    except Exception:
        print("FFmpeg/FFprobe not found.")
        sys.exit(1)

    target = None
    while True:
        display_ui(target)
        choice = input("Choice [1-4]: ").strip()
        if choice == '1':
            target = select_file(target)
        elif choice == '2':
            if not target:
                print("No file selected.")
            else:
                try:
                    w = int(input("Width: ").strip())
                    h = int(input("Height: ").strip())
                    fps = int(input("FPS [1]: ").strip() or 1)
                    fn = input(f"Output MP4 [{DEFAULT_MP4_FILENAME}]: ").strip() or DEFAULT_MP4_FILENAME
                    if not fn.lower().endswith('.mp4'):
                        fn += '.mp4'
                    encode_mp4(target, fn, w, h, fps)
                except Exception as e:
                    print(f"Error: {e}")
            input("Press Enter to continue...")
        elif choice == '3':
            if not target or not target.lower().endswith('.mp4'):
                print("Select an MP4 file first.")
            else:
                fn = input(f"Output file [{DEFAULT_DECRYPTED_FILENAME}]: ").strip() or DEFAULT_DECRYPTED_FILENAME
                decode_mp4(target, fn)
            input("Press Enter to continue...")
        elif choice == '4':
            break
        else:
            print("Invalid choice.")
            input("Press Enter to continue...")

if __name__ == '__main__':
    main()
