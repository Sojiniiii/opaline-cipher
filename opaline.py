import os
import math
import time
import struct
import wave
from tkinter import filedialog, Tk
from PIL import Image, UnidentifiedImageError

# --- Configuration ---
def defaults():
    return ("image.png", "audio.wav", 2) #Default image name, default file name, and audio format (1 = mono, 2 = stereo)
# Do not change the following if you don't know what you're doing!
SIZE_STRUCT_FORMAT = '>Q'
SIZE_BYTES_LEN = struct.calcsize(SIZE_STRUCT_FORMAT)

# --- Loading Bar ---
_last_progress_print_time = 0
_animation_chars = ['|', '/', '-', '\\']
_animation_idx = 0

def _update_progress_display(percent, message):
    global _animation_idx
    char = _animation_chars[_animation_idx]
    print(f"\r{message}: {char} {percent:.2f}% complete", end='', flush=True)
    _animation_idx = (_animation_idx + 1) % len(_animation_chars)

def start_progress(message="Processing..."):
    global _last_progress_print_time, _animation_idx
    _last_progress_print_time = time.time() # Initialize time
    _animation_idx = 0
    # Printing 0% at start is not really necessary

def report_progress(current_item, total_items, message="Processing...", interval=0.1):
    global _last_progress_print_time
    if total_items == 0:
        return

    now = time.time()
    # Update on first item (current_item could be 0-indexed or 1-indexed, handle current_item relative to total, assumes it is 1-indexed)
    if current_item == 1 or current_item == total_items or \
       (now - _last_progress_print_time >= interval):
        percent = (current_item / total_items) * 100
        _update_progress_display(percent, message)
        _last_progress_print_time = now

def end_progress(message="Processing..."):
    print(f"\r{message}: Done.                            ", flush=True)


# --- Key functions ---
def phk(key_str):
    # Parses a string of hexadecimal values into a list of integers. PHK stands for Parse Hex Key.
    if not key_str:
        return []
    keys = []
    try:
        for part in key_str.split():
            cleaned_part = part.strip()
            if cleaned_part:
                keys.append(int(cleaned_part, 16))
        if not all(0 <= k <= 255 for k in keys):
            print("Warning: Keys should be valid hex bytes (00-FF). Some values might be invalid.")
        return keys
    except ValueError:
        print("Error: Invalid hexadecimal value in key. Using no key.")
        return []

# --- Conversion functions ---
def rgb_to_hex(rgb):
    # Converts an RGB tuple to a 6-character hex string.
    if not isinstance(rgb, (tuple, list)) or len(rgb) < 3:
        return "000000"
    try:
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
        return 0, 0, 0

# --- Conversion functions ---
def bytes_to_rgb_list(data_bytes):
    rgb_list = []
    num_bytes = len(data_bytes)
    if num_bytes == 0:
        return rgb_list

    operation_message = "Converting bytes to RGB"
    start_progress(operation_message)
    # Initial display for 0% or first chunk
    report_progress(0, num_bytes, operation_message) # Report 0 bytes processed out of num_bytes

    for i in range(0, num_bytes, 3):
        chunk = data_bytes[i:i + 3]
        if len(chunk) == 3:
            rgb_list.append(tuple(chunk))
        elif len(chunk) == 2:
            rgb_list.append((chunk[0], chunk[1], 0))
        elif len(chunk) == 1:
            rgb_list.append((chunk[0], 0, 0))
        
        # Report progress: current_item is bytes processed (i + len(chunk) or similar)
        report_progress(min(i + 3, num_bytes), num_bytes, operation_message)
    
    end_progress(operation_message)
    return rgb_list

def rgb_list_to_bytes(rgb_list):
    byte_list = bytearray()
    total_pixels = len(rgb_list)
    if total_pixels == 0:
        return bytes(byte_list)

    operation_message = "Converting RGB to bytes"
    start_progress(operation_message)
    report_progress(0, total_pixels, operation_message) # Report 0 pixels processed

    for idx, rgb in enumerate(rgb_list):
        try:
            r, g, b = [max(0, min(255, int(x))) for x in rgb[:3]]
            byte_list.extend(bytes([r, g, b]))
        except (ValueError, TypeError, IndexError):
            byte_list.extend(bytes([0, 0, 0]))
            print(f"Warning: Encountered invalid pixel data {rgb}, replacing with black.")
        
        report_progress(idx + 1, total_pixels, operation_message)

    end_progress(operation_message)
    return bytes(byte_list)

# --- Encryption logic (Generic for byte-representable data) ---
def cipher(data_bytes, keys, encrypting=True):
    if not keys:
        return data_bytes

    data_len = len(data_bytes)
    if data_len == 0:
        return data_bytes
        
    processed_bytes = bytearray(data_len)
    key_len = len(keys)

    if key_len == 0: # Should be caught by 'if not keys'
        return data_bytes

    op = (lambda a, b: (a + b) % 256) if encrypting else (lambda a, b: (a - b + 256) % 256)
    
    op_message = "Encrypting data stream" if encrypting else "Decrypting data stream"
    start_progress(op_message)
    report_progress(0, data_len, op_message) # Report 0 bytes processed

    # Determine update frequency for progress bar
    update_interval_bytes = max(1, data_len // 200) # Aim for ~200 updates
    if data_len > 1024 * 1024 : # For files > 1MB, update at least every 64KB
         update_interval_bytes = max(update_interval_bytes, 65536)


    for i, byte in enumerate(data_bytes):
        processed_bytes[i] = op(byte, keys[i % key_len])
        if (i + 1) % update_interval_bytes == 0 or (i + 1) == data_len:
            report_progress(i + 1, data_len, op_message)
            
    end_progress(op_message)
    return bytes(processed_bytes)

# --- Image Handling ---
def load_image(filepath):
    img = None  # Initialize img to None
    try:
        img = Image.open(filepath)
    except FileNotFoundError:
        print(f"Error: Image file not found at '{filepath}'")
        return None, None
    except UnidentifiedImageError:
        print(f"Error: Cannot identify image file '{filepath}'. Is it a valid image format?")
        return None, None
    except Exception as e: # Catch other Image.open errors
        print(f"Error opening image '{filepath}': {e}")
        return None, None

    try:
        img_dimensions = img.size

        if img.mode == 'RGB':
            pixels = list(img.getdata())
        else:
            # print(f"Image mode '{img.mode}' is not RGB. Attempting conversion...") # Less verbose
            try:
                img_converted = img.convert('RGB')
                pixels = list(img_converted.getdata())
                img_converted.close() # Close the temporary converted image
            except Exception as e_convert:
                print(f"\nError: Could not convert image '{filepath}' (mode: {img.mode}) to RGB: {e_convert}.")
                # img.close() is handled in finally
                return None, None
        
        # img.close() is handled in finally
        return pixels, img_dimensions
    except Exception as e_process:
        print(f"Error processing image data from '{filepath}': {e_process}")
        return None, None
    finally:
        if img: # Ensure img was successfully opened before trying to close
            img.close()


def prep_image(data_bytes, key_list, output_image_path, target_dims=None):
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)
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
            print(f"Error: Data ({required_pixels} pixels required) exceeds target image capacity ({width*height} pixels).")
            print("Encryption aborted.")
            return False

    total_pixels = width * height
    padding_needed = total_pixels - required_pixels
    padded_rgb = rgb_data + [(0, 0, 0)] * padding_needed

    print(f"Creating image '{output_image_path}'...")
    try:
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
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)
    if not encrypted_bytes and len(data_bytes) > 0 and key_list : # Cipher might return empty if data was empty
        print("Error: Data became empty after ciphering. Cannot create WAV.")
        return False

    num_channels = defaults()[2]
    bytes_per_frame = num_channels * sample_width

    # Corrected padding logic
    if bytes_per_frame > 0 : # Avoid division by zero if params are bad
        remainder = len(encrypted_bytes) % bytes_per_frame
        if remainder != 0:
            padding_bytes_to_add = bytes_per_frame - remainder
            encrypted_bytes += b'\x00' * padding_bytes_to_add # Append correct number of null bytes
            # print(f"Padded data with {padding_bytes_to_add} zero bytes for WAV frame alignment.") # Optional
    else:
        print(f"Error: Invalid WAV parameters (bytes_per_frame is {bytes_per_frame}). Cannot proceed.")
        return False


    num_frames = len(encrypted_bytes) // bytes_per_frame if bytes_per_frame > 0 else 0

    # Edge case: if encrypted_bytes is non-empty but not enough for one frame after padding
    if len(encrypted_bytes) > 0 and num_frames == 0:
        print(f"Warning: Data is too short for even a single WAV frame after padding (data length: {len(encrypted_bytes)}, bytes/frame: {bytes_per_frame}).")
        # Depending on wave library, this might still error or create an empty/invalid WAV.
        # Forcing num_frames to 0 if encrypted_bytes is effectively empty for WAV purposes.
        if len(encrypted_bytes) < bytes_per_frame: # Ensure it's truly not enough
             print("Resulting WAV file may be empty or invalid.")


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
        # print(f"  Details: num_frames={num_frames}, len(encrypted_bytes)={len(encrypted_bytes)}, bytes_per_frame={bytes_per_frame}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during WAV creation: {e}")
        return False

def load_wav(filepath):
    try:
        with wave.open(filepath, 'rb') as wf:
            print(f"Loading WAV: {wf.getnchannels()} channels, {wf.getframerate()} Hz, {wf.getsampwidth()} bytes/sample")
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

# --- Core encryption/decryption Logic ---
def encrypt_file(target_data_file, output_media_path, media_type, key_str):
    if not target_data_file:
        print("Error: No target data file selected for encryption input. Use 'Select Target' first.")
        return

    print(f"Attempting to encrypt data file: {target_data_file}")
    try:
        with open(target_data_file, 'rb') as f:
            file_bytes = f.read()
        original_size = len(file_bytes)
        print(f"Read {original_size} bytes from the file.")
        if original_size == 0:
            print("Warning: Target file is empty. Encrypted media will represent an empty file.")
    except FileNotFoundError:
        print(f"Error: Target data file '{target_data_file}' not found.")
        return
    except Exception as e:
        print(f"Error reading data file: {e}")
        return

    keys = phk(key_str)

    try:
        size_bytes = struct.pack(SIZE_STRUCT_FORMAT, original_size)
    except struct.error as e:
        print(f"Error packing file size ({original_size}): {e}. Cannot proceed.")
        return
    
    data_to_process = size_bytes + file_bytes
    success = False
    
    print(f"\nStarting file encryption to {media_type.upper()}...")
    start_time = time.time()

    if media_type == 'png':
        target_dims = None
        if os.path.exists(output_media_path):
            preserve = input(f"Output image '{output_media_path}' exists. Preserve its dimensions? (y/n, default = n): ").strip().lower()
            if preserve == 'y':
                print("Attempting to use existing image dimensions...")
                _, existing_dims = load_image(output_media_path) # load_image handles its own prints
                if existing_dims:
                    target_dims = existing_dims
                else:
                    print("Could not load existing image dimensions. Using auto-resize.")
        success = prep_image(data_to_process, keys, output_media_path, target_dims)

    elif media_type == 'wav':
        sr, sw = 44100, 2 # Defaults
        try:
            sr_str = input(f"Enter sample rate (e.g., 44100, default {sr}): ")
            sw_str = input(f"Enter sample width bytes (1 for 8-bit, 2 for 16-bit, default {sw}): ")
            
            if sr_str: sr = int(sr_str)
            if sw_str: sw = int(sw_str)

            if sw not in [1, 2]:
                raise ValueError("Sample width must be 1 or 2")
            if sr <= 0:
                raise ValueError("Sample rate must be positive")

        except ValueError as e:
            print(f"Invalid input: {e}. Using defaults ({sr} Hz, {sw*8}-bit).")
            # sr, sw already set to defaults
        
        success = prep_wav(data_to_process, keys, output_media_path, sample_rate=sr, sample_width=sw)

    else:
        print(f"Error: Unknown media type '{media_type}' for encryption.")
        return

    end_time = time.time()
    if success:
        print(f"File encryption finished in {end_time - start_time:.4f} seconds.")
    else:
        print("File encryption failed.")


def decrypt_file(input_media_path, media_type, key_str, output_filepath):
    if not output_filepath:
        print("Output filename cannot be empty. Aborting decryption.")
        return

    print(f"\nAttempting decryption from {media_type.upper()} '{input_media_path}' to new file '{output_filepath}'...")
    start_time = time.time()

    keys = phk(key_str)
    raw_data_bytes = None

    if media_type == 'png':
        pixels, _ = load_image(input_media_path) # load_image handles its prints/errors
        if pixels is None:
            print("File decryption failed (could not load image pixels).")
            return
        raw_data_bytes = rgb_list_to_bytes(pixels) # This shows progress

    elif media_type == 'wav':
        raw_data_bytes = load_wav(input_media_path) # load_wav handles its prints/errors
        if raw_data_bytes is None:
            print("File decryption failed (could not load WAV data).")
            return
    else:
        print(f"Error: Unknown media type '{media_type}' for decryption.")
        return

    if not raw_data_bytes: # Should be caught by earlier checks
        print("Error: Failed to extract raw byte data from the media file.")
        return

    all_decrypted_bytes = cipher(raw_data_bytes, keys, encrypting=False) # This shows progress

    if len(all_decrypted_bytes) < SIZE_BYTES_LEN:
        print(f"Error: Decrypted data stream is too short ({len(all_decrypted_bytes)} bytes) to contain file size info ({SIZE_BYTES_LEN} bytes).")
        print(" Possible reasons: incorrect key, corrupted file, file not created by this program, or incorrect media type selected.")
        return

    # print("Extracting original file size and data...") # Quick operation
    try:
        size_bytes = all_decrypted_bytes[:SIZE_BYTES_LEN]
        original_size = struct.unpack(SIZE_STRUCT_FORMAT, size_bytes)[0]
        # print(f"Extracted original file size: {original_size} bytes.") # Can be verbose

        extracted_file_data = all_decrypted_bytes[SIZE_BYTES_LEN:]

        if len(extracted_file_data) < original_size:
            print(f"Warning: Actual data length ({len(extracted_file_data)}) is less than expected original size ({original_size}).")
            print("File might be incomplete or corrupted.")
            final_file_data = extracted_file_data
        else:
            final_file_data = extracted_file_data[:original_size]

    except struct.error as e:
        print(f"Error unpacking file size: {e}. Media file data may be corrupted, the key might be wrong, or it's not an Opaline file.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data extraction: {e}")
        return

    print(f"Attempting to write {len(final_file_data)} bytes to new file '{output_filepath}'...")
    try:
        with open(output_filepath, 'wb') as f:
            f.write(final_file_data)
        end_time = time.time()
        print(f"Finished writing decrypted data to '{output_filepath}' in {end_time - start_time:.4f} seconds.")
    except Exception as e:
        print(f"Error writing decrypted file '{output_filepath}': {e}")


# --- File Selection ---
def select_target_file():
    print("\nPlease select the target file (file to encrypt or media file to decrypt)...")
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected_path = filedialog.askopenfilename(title="Select Target File")
    root.destroy()

    if selected_path:
        print(f"\nTarget file set to: {selected_path}")
        return selected_path
    else:
        print("\nNo file selected; target remains unset.")
        return None

# --- User Interface ---
def display_ui(target_data_file):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n-=- Opaline by Alex Hall -=-\n")
    print("-" * 60)
    print(f"Current target: {target_data_file if target_data_file else 'unset'}")
    print("-" * 60)
    print("Choose an operation:")
    print("  1. Select target")
    print("  2. Encrypt target")
    print("  3. Decrypt target")
    print("  4. Exit")
    print("-" * 60)


def main():
    target_file = None
    default_img_name, default_wav_name, _ = defaults() # Use tuple unpacking

    while True:
        display_ui(target_file)
        choice = input("Enter choice (1-4): ")

        try:
            n = int(choice)
            os.system('cls' if os.name == 'nt' else 'clear') # Clear after input, before processing

            if n == 1:
                selected = select_target_file()
                if selected:
                    target_file = selected

            elif n == 2:
                if not target_file:
                    print("Error: No target file selected.")
                    print("Please use option 1 first to select the file you want to encrypt.")
                    input("\nPress Enter to continue...")
                    continue

                print("-" * 60)
                print("Choose an output format: ")
                print("  1. Image (png)")
                print("  2. Audio (wav)")
                print("  3. Back")
                print("-" * 60)

                media_choice_str = input("Choose output format (default = image): ")
                media_choice = 1 # Default to image
                if media_choice_str:
                    try:
                        media_choice = int(media_choice_str)
                    except ValueError:
                        print("\nInvalid choice. Defaulting to image.")
                
                output_media_path = ""
                media_type = ""

                if media_choice == 1:
                    media_type = 'png'
                    output_media_path = input(
                        f"Enter output PNG filename (blank uses '{default_img_name}'): ").strip() or default_img_name
                elif media_choice == 2:
                    media_type = 'wav'
                    output_media_path = input(
                        f"Enter output WAV filename (blank uses '{default_wav_name}'): ").strip() or default_wav_name
                elif media_choice == 3:
                    continue
                else:
                     print("\nInvalid format choice. Returning to main menu.")
                     input("\nPress Enter to continue...")
                     continue

                key = input("Enter optional encryption key (hex values separated by spaces, e.g., '1F A0 33'), or leave blank for no encryption: ").strip()
                encrypt_file(target_file, output_media_path, media_type, key)
                input("\nPress Enter to continue...")

            elif n == 3:
                if not target_file:
                    print("Error: No target file selected.")
                    print("Please use option 1 first to select the .png or .wav file you want to decrypt.")
                    input("\nPress Enter to continue...")
                    continue

                _, ext = os.path.splitext(target_file)
                ext = ext.lower()[1:]
                if ext not in ['png', 'wav']:
                    print(f"Error: Cannot determine supported media type from extension '{ext}'.")
                    print(" Please select a png or wav file that you know was created by Opaline.")
                    input("\nPress Enter to continue...")
                    continue
                
                media_type = ext
                key = input("Enter optional decryption key used during encryption (hex values separated by spaces), or leave blank if no key was used: ").strip()
                print("\nThis next step is important. You must enter the a file name and the correct file extension.")
                out_file = input(
                    "Enter desired filename for the decrypted file (e.g., 'document.txt', 'archive.zip'): ").strip()

                if not out_file:
                    print("\nNo output filename provided. Decryption cancelled.")
                else:
                    decrypt_file(target_file, media_type, key, out_file)
                input("\nPress Enter to continue...")
            
            elif n == 4:
                print("Exiting Opaline. Goodbye! :)")
                break   
            else:
                print(f"\nInvalid choice ({n}). Please enter a number between 1 and 4.")
                input("\nPress Enter to continue...")

        except ValueError:
            print("\nInvalid input. Please enter a number (1-4).")
            input("Press Enter to continue...")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user (Ctrl+C). Exiting.")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred in the main loop: {e}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
