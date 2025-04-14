import os
import math
import time
import struct
import wave
from tkinter import filedialog, Tk
from PIL import Image, UnidentifiedImageError

# --- Configuration ---
DEFAULT_IMAGE_FILENAME = "image.png"
DEFAULT_WAV_FILENAME = "audio.wav"
SIZE_STRUCT_FORMAT = '>Q'
SIZE_BYTES_LEN = struct.calcsize(SIZE_STRUCT_FORMAT)

# --- Key functions ---
def phk(key_str):
    # Parses a string of hexadecimal values into a list of integers. PHK stands for Parse Hex Key.
    if not key_str:
        return []
    keys = []
    try:
        for part in key_str.split():
            keys.append(int(part.strip(), 16))
        if not all(0 <= k <= 255 for k in keys):
            print("Warning: Keys should be valid hex bytes (00-FF).")
        return keys
    except ValueError:
        print("Error: Invalid hexadecimal value in key. Using no key.")
        return []

# --- Conversion functions (Image) ---
def rgb_to_hex(rgb):
    # Converts an RGB tuple to a 6-character hex string.
    if not isinstance(rgb, (tuple, list)) or len(rgb) < 3:
        return "000000"
    try:
        # Ensure values are within byte range
        r, g, b = [max(0, min(255, int(x))) for x in rgb[:3]]
        return f'{r:02x}{g:02x}{b:02x}'
    except (ValueError, TypeError):
        return "000000"

def hex_to_rgb(hex_chunk):
    # Converts a 6-character hex string (or shorter) to an RGB tuple.
    hex_chunk = hex_chunk.ljust(6, '0')
    try:
        r = int(hex_chunk[0:2], 16)
        g = int(hex_chunk[2:4], 16)
        b = int(hex_chunk[4:6], 16)
        return r, g, b
    except ValueError:
        return 0, 0, 0  # Return black on error

def bytes_to_rgb_list(data_bytes):
    # Converts bytes to a list of RGB tuples.
    hex_data = data_bytes.hex()
    rgb_list = []
    # Process in chunks of 6 hex characters (3 bytes)
    for i in range(0, len(hex_data), 6):
        hex_chunk = hex_data[i:i + 6]
        rgb_list.append(hex_to_rgb(hex_chunk))
    return rgb_list

def rgb_list_to_bytes(rgb_list):
    # Converts a list of RGB tuples back to bytes.
    hex_list = [rgb_to_hex(rgb) for rgb in rgb_list]
    hex_string = "".join(hex_list)
    try:
        return bytes.fromhex(hex_string)
    except ValueError as e:
        print(f"Error converting final hex string to bytes: {e}. Data likely corrupted.")
        # Attempt to recover by ignoring the problematic character if possible
        try:
            return bytes.fromhex(hex_string[:-1])
        except ValueError:
            return b''

# --- Encryption logic (Generic for byte-representable data) ---
def cipher(data_bytes, keys, encrypting=True):
    # Encrypts or decrypts raw bytes using a list of keys (byte values 0-255).
    if not keys:
        return data_bytes
    processed_bytes = bytearray()
    key_len = len(keys)
    op = (lambda a, b: (a + b) % 256) if encrypting else (lambda a, b: (a - b + 256) % 256)
    for i, byte in enumerate(data_bytes):
        processed_bytes.append(op(byte, keys[i % key_len]))
    return bytes(processed_bytes)

# --- Image Handling ---
def load_image(filepath):
    # Loads an image file and returns its pixel data (list of RGB tuples) and dimensions.
    try:
        img = Image.open(filepath)
        original_size = img.size
        if img.mode != 'RGB':
            try:
                img = img.convert('RGB')
            except Exception as e:
                print(f"Warning: Could not convert image mode {img.mode} to RGB: {e}.")

        pixels = list(img.getdata())
        img.close()
        return pixels, original_size

    except FileNotFoundError:
        print(f"Error: Image file not found at '{filepath}'")
        return None, None
    except UnidentifiedImageError:
        print(f"Error: Cannot identify image file. Is '{filepath}' a valid image?")
        return None, None
    except Exception as e:
        print(f"Error opening or reading image '{filepath}': {e}")
        return None, None

def prep_image(data_bytes, key_list, output_image_path, target_dims=None):
    # Encrypts byte data and saves it into an image file.
    print("Encrypting data with cipher (if key provided)...")
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)

    print("Converting bytes to RGB pixel data...")
    rgb_data = bytes_to_rgb_list(encrypted_bytes)
    required_pixels = len(rgb_data)

    width, height = 0, 0
    use_auto_resize = target_dims is None

    if use_auto_resize:
        print("Calculating optimal image size...")
        width = max(1, math.ceil(math.sqrt(required_pixels)))
        height = max(1, math.ceil(required_pixels / width))
        print(f"Auto-calculated image size: {width}x{height}")
    else:
        width, height = target_dims
        print(f"Using specified dimensions: {width}x{height}")
        if required_pixels > width * height:
            print(f"Error: Data ({required_pixels} pixels) exceeds target image capacity ({width*height} pixels).")
            print("Encryption aborted. Try without preserving dimensions or use a larger image.")
            return False

    total_pixels = width * height
    padding_needed = total_pixels - required_pixels
    # Pad with black pixels if the data doesn't fill the image completely
    padded_rgb = rgb_data + [(0, 0, 0)] * padding_needed

    print(f"Creating image '{output_image_path}'...")
    try:
        # Creates a new RGB image, packs the pixel data into it, and saves it
        img = Image.new("RGB", (width, height))
        img.putdata(padded_rgb)
        img.save(output_image_path, format='PNG')
        img.close()
        print("Image created/updated successfully.")
        return True
    except Exception as e:
        print(f"Error creating or saving image: {e}")
        return False

# --- WAV Handling ---
def prep_wav(data_bytes, key_list, output_wav_path, sample_rate=44100, sample_width=2):
    # Encrypts byte data and saves it into a WAV audio file.
    print("Encrypting data with cipher (if key provided)...")
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)

    # Determine WAV parameters
    num_channels = 1  # Mono
    # sample_width = 2 # Bytes per sample (1=8-bit, 2=16-bit)
    bytes_per_frame = num_channels * sample_width

    # Pad data to align with sample width
    remainder = len(encrypted_bytes) % sample_width
    if remainder != 0:
        padding_needed = sample_width - remainder
        encrypted_bytes += b'\x00' * padding_needed
        print(f"Padded data with {padding_needed} zero bytes for WAV frame alignment.")

    num_frames = len(encrypted_bytes) // bytes_per_frame

    print(f"Creating WAV file '{output_wav_path}'...")
    try:
        with wave.open(output_wav_path, 'wb') as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.setnframes(num_frames)
            wf.writeframes(encrypted_bytes)
        print("WAV file created successfully.")
        return True
    except wave.Error as e:
        print(f"Error writing WAV file: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during WAV creation: {e}")
        return False

def load_wav(filepath):
    # Loads a WAV file and returns its raw frame data as bytes.
    try:
        with wave.open(filepath, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            return frames
    except FileNotFoundError:
        print(f"Error: WAV file not found at '{filepath}'")
        return None
    except wave.Error as e:
        print(f"Error reading WAV file '{filepath}': {e}. Is it a valid WAV file?")
        return None
    except Exception as e:
        print(f"Error opening or reading WAV file '{filepath}': {e}")
        return None

# --- Core Encryption/Decryption Logic ---
def encrypt_file(target_data_file, output_media_path, media_type, key_str):
    # Handles encrypting the target
    if not target_data_file:
        print("Error: No target data file selected for encryption input. Use 'Select Target' first.")
        return

    print(f"Attempting to encrypt data file: {target_data_file}")
    try:
        with open(target_data_file, 'rb') as f:
            file_bytes = f.read()
        original_size = len(file_bytes)
        print(f"Read {original_size} bytes from the file.")
    except FileNotFoundError:
        print(f"Error: Target data file '{target_data_file}' not found.")
        return
    except Exception as e:
        print(f"Error reading data file: {e}")
        return

    keys = phk(key_str)

    # Prepend the original file size to the data
    try:
        size_bytes = struct.pack(SIZE_STRUCT_FORMAT, original_size)
    except struct.error as e:
        print(f"Error packing file size ({original_size}): {e}. Cannot proceed.")
        return
    data_to_process = size_bytes + file_bytes

    print(f"Starting file encryption to {media_type.upper()}...")
    start_time = time.time()
    success = False

    if media_type == 'image':
        target_dims = None
        if os.path.exists(output_media_path):
            preserve = input(f"Output image '{output_media_path}' exists. Preserve its dimensions? (y/n, default n): ").strip().lower()
            if preserve == 'y':
                print("Attempting to use existing image dimensions...")
                _, existing_dims = load_image(output_media_path)
                if existing_dims:
                    target_dims = existing_dims
                else:
                    print("Could not load existing image dimensions. Using auto-resize.")
        success = prep_image(data_to_process, keys, output_media_path, target_dims)

    elif media_type == 'wav':
        try:
            sr = int(input("Enter sample rate (e.g., 44100, default): ") or "44100")
            sw = int(input("Enter sample width bytes (1 for 8-bit, 2 for 16-bit, default 2): ") or "2")
            if sw not in [1, 2]:
                raise ValueError("Sample width must be 1 or 2")
        except ValueError as e:
            print(f"Invalid input: {e}. Using defaults (44100 Hz, 16-bit).")
            sr, sw = 44100, 2
        success = prep_wav(data_to_process, keys, output_media_path, sample_rate=sr, sample_width=sw)

    else:
        # If this case is reached, something bad has happened or you have messed something up :(
        print(f"Error: Unknown media type '{media_type}' for encryption.")
        return

    end_time = time.time()
    if success:
        print(f"File encryption finished in {end_time - start_time:.4f} seconds.")
    else:
        print("File encryption failed.")

def decrypt_file(input_media_path, media_type, key_str, output_filepath):
    """Handles decrypting a file from the specified media type."""
    if not output_filepath:
        print("Output filename cannot be empty. Aborting decryption.")
        return

    print(f"Attempting decryption from {media_type.upper()} '{input_media_path}' to new file '{output_filepath}'...")
    start_time = time.time()

    keys = phk(key_str)
    
    # 1. Get raw byte data
    raw_data_bytes = None
    if media_type == 'image':
        pixels, _ = load_image(input_media_path)
        if pixels is None:
            print("File decryption failed (could not load image pixels).")
            return
        print("Converting pixels to byte stream...")
        raw_data_bytes = rgb_list_to_bytes(pixels)

    elif media_type == 'wav':
        raw_data_bytes = load_wav(input_media_path)
        if raw_data_bytes is None:
            print("File decryption failed (could not load WAV data).")
            return

    else:
        # sina kama ni la ni li ike a
        print(f"Error: Unknown media type '{media_type}' for decryption.")
        return

    if not raw_data_bytes:
        print("Error: Failed to extract raw byte data from the media file.")
        return

    # 2. Decrypt bytes
    print("Decrypting byte stream with cipher (if key provided)...")
    all_decrypted_bytes = cipher(raw_data_bytes, keys, encrypting=False)

    # 3. Extract size and original data
    if len(all_decrypted_bytes) < SIZE_BYTES_LEN:
        print(f"Error: Decrypted data stream is too short ({len(all_decrypted_bytes)} bytes) for file size info ({SIZE_BYTES_LEN} bytes).")
        print(" Possible reasons: incorrect key, corrupted file, or not an Opaline file.")
        return

    print("Extracting original file size and data...")
    try:
        size_bytes = all_decrypted_bytes[:SIZE_BYTES_LEN]
        original_size = struct.unpack(SIZE_STRUCT_FORMAT, size_bytes)[0]
        print(f"Extracted original file size: {original_size} bytes.")

        extracted_file_data = all_decrypted_bytes[SIZE_BYTES_LEN:]

        # 4. Truncate data to original size
        if len(extracted_file_data) < original_size:
            print(f"Warning: Actual data length ({len(extracted_file_data)}) is less than expected size ({original_size}). File might be incomplete or corrupted.")
            final_file_data = extracted_file_data
        else:
            final_file_data = extracted_file_data[:original_size]

    except struct.error as e:
        print(f"Error unpacking file size: {e}. Image/Audio/Video data may be corrupted or key is wrong.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data extraction: {e}")
        return

    # 5. Write the decrypted data to the output file
    print(f"Attempting to write {len(final_file_data)} bytes to new file '{output_filepath}'...")
    try:
        with open(output_filepath, 'wb') as f:
            f.write(final_file_data)
        end_time = time.time()
        print(f"Finished writing decrypted data to '{output_filepath}' in {end_time - start_time:.4f} seconds.")
        print("REMINDER: Ensure the filename has the correct extension to open it properly.")
    except Exception as e:
        end_time = time.time()
        print(f"Error writing decrypted file '{output_filepath}': {e}")

def select_target_file():
    # Lets user select the target
    print("\nPlease select the target file (the file you want to encrypt/hide)")

    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected_path = filedialog.askopenfilename(
        title="Select Target File to Encrypt"
    )
    root.destroy()

    if selected_path:
        print(f"\nTarget file set to: {selected_path}")
        return selected_path
    else:
        print("\nNo file selected; target remains unset.")
        return None

# --- User Interface ---
def display_ui(target_data_file):
    # Clears screen and displays the main menu.
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n-=- Opaline by Alex Hall -=-\n")
    print("-" * 60)
    print(f"Current target: {target_data_file if target_data_file else 'unset (choose with option 1)'}")
    print("-" * 60)
    # Removed default file
    print("Choose an operation:")
    print("  1. Select target")
    print("  2. Encrypt target")
    print("  3. Decrypt target")
    print("  4. Exit")
    print("-" * 60)

def main():
    # Main UI loop
    target_file = None
    img_path_default = DEFAULT_IMAGE_FILENAME
    wav_path_default = DEFAULT_WAV_FILENAME

    while True:
        display_ui(target_file)
        choice = input("Enter choice (1-4): ")

        try:
            n = int(choice)
            os.system('cls' if os.name == 'nt' else 'clear')
            if n == 1:
                selected = select_target_file()
                if selected:
                    target_file = selected
            elif n == 2:
                if not target_file:
                    print("Error: No target file selected. Please use option 1 first.")
                    input("\nPress Enter to continue...")
                    continue
                
                print("-" * 60)
                print("Choose an output format: ")
                print("  1. Image (png)")
                print("  2. Audio (waveform)")
                print("-" * 60)

                media_choice = input("Choose output format (image or wav) [default: image]: ") or 1

                try:
                    c = int(media_choice)
                except ValueError:
                    print("\nInvalid choice. Defaulting to image.")
                    media_choice = 1

                output_media_path = ""
                media_type = ""

                if media_choice == 1:
                    media_type = 'image'
                    output_media_path = input(
                        f"Enter output png filename (blank uses '{img_path_default}'): ").strip() or img_path_default
                elif media_choice == 2:
                    media_type = 'wav'
                    output_media_path = input(
                        f"Enter output wav filename (blank uses '{wav_path_default}'): ").strip() or wav_path_default
                    
                key = input("Enter optional encryption key (hex values separated by spaces), or leave blank: ").strip()
                encrypt_file(target_file, output_media_path, media_type, key)

            elif n == 3:
                ext = target_file[-4:].lower()
                media_type = ""

                if ext == '.png':
                    media_type = 'image'
                elif ext == '.wav':
                    media_type = 'wav'
                else:
                    print(f"Error: Cannot determine media type from extension '{ext}'.")
                    print(" Please use a file with .png or .wav extension.")
                    input("\nPress Enter to continue...")
                    continue

                key = input("Enter optional decryption key (hex values separated by spaces), or leave blank: ").strip()
                out_file = input(
                    "Enter desired filename for the DECRYPTED file (e.g., 'doc.txt', 'archive.zip'): ").strip()
                decrypt_file(target_file, media_type, key, out_file)
            elif n == 4:
                print("Exiting Opaline. Goodbye! :)")
                break
            else:
                print("\nInvalid choice. Please enter a number between 1 and 5.")
        except ValueError:
            print("\nInvalid input. Please enter a number.")
            input("Press Enter to continue...")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user. Exiting.")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred in the main loop: {e}")
            import traceback
            traceback.print_exc()
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()
