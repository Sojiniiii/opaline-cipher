import os
import math
import time
import struct
import wave
from tkinter import filedialog, Tk
from PIL import Image, UnidentifiedImageError

# --- Configuration ---
DEFAULT_PNG_FILENAME = "image.png"
DEFAULT_WAV_FILENAME = "audio.wav"
# - Do not change if you don't know what you're doing -
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
            # Cleaning the part (ensuring it is stripped and removing double spaces)
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
        # Values must be within byte range
        r, g, b = [max(0, min(255, int(x))) for x in rgb[:3]]
        return f'{r:02x}{g:02x}{b:02x}'
    except (ValueError, TypeError):
        return "000000"

def hex_to_rgb(hex_chunk):
    # Converts a 6-character hex string (or shorter) to an RGB tuple.
    hex_chunk = hex_chunk.ljust(6, '0') # Pad with '0' if shorter than 6 chars
    try:
        r = int(hex_chunk[0:2], 16)
        g = int(hex_chunk[2:4], 16)
        b = int(hex_chunk[4:6], 16)
        return r, g, b
    except ValueError:
        return 0, 0, 0  # Return black on error

# --- Conversion functions ---
def bytes_to_rgb_list(data_bytes):
    # Converts bytes directly to a list of RGB tuples without intermediate hex strings.
    rgb_list = []
    num_bytes = len(data_bytes)
    for i in range(0, num_bytes, 3):
        chunk = data_bytes[i:i + 3]
        if len(chunk) == 3:
            rgb_list.append(tuple(chunk)) # Directly use the byte values
        elif len(chunk) == 2:
            # Pad with a zero byte for the last pixel if data length is not multiple of 3
            rgb_list.append((chunk[0], chunk[1], 0))
        elif len(chunk) == 1:
            # Pad with two zero bytes
            rgb_list.append((chunk[0], 0, 0))
    return rgb_list

def rgb_list_to_bytes(rgb_list):
    # Converts a list of RGB tuples back to bytes directly.
    byte_list = bytearray()
    for rgb in rgb_list:
        # RGB values must be valid bytes (0-255)
        try:
            # Clamp values just in case PIL provides something unexpected, though it shouldn't
            r, g, b = [max(0, min(255, int(x))) for x in rgb[:3]]
            byte_list.extend(bytes([r, g, b]))
        except (ValueError, TypeError, IndexError):
            # Append black pixel bytes on error
            byte_list.extend(bytes([0, 0, 0]))
            print(f"Warning: Encountered invalid pixel data {rgb}, replacing with black.")

    return bytes(byte_list) # Convert final bytearray to bytes

# --- Encryption logic (Generic for byte-representable data) ---
def cipher(data_bytes, keys, encrypting=True):
    # Encrypts or decrypts raw bytes using a list of keys (byte values 0-255).
    if not keys:
        return data_bytes # Return original data if no key is provided

    processed_bytes = bytearray(len(data_bytes)) # Pre-allocate bytearray for efficiency
    key_len = len(keys)

    if key_len == 0: # Should be caught by the 'if not keys' check, but belts and suspenders
        return data_bytes

    # Choose operation once outside the loop
    op = (lambda a, b: (a + b) % 256) if encrypting else (lambda a, b: (a - b + 256) % 256)

    for i, byte in enumerate(data_bytes):
        processed_bytes[i] = op(byte, keys[i % key_len])

    return bytes(processed_bytes)

# --- Image Handling ---
def load_image(filepath):
    # Loads an image file and returns its pixel data (list of RGB tuples) and dimensions.
    try:
        img = Image.open(filepath)
        original_size = img.size
        # Ensure image is in RGB mode for consistent processing
        if img.mode != 'RGB':
            print(f"Converting image mode '{img.mode}' to 'RGB'.")
            try:
                # Use convert instead of trying to handle exceptions for specific modes
                img = img.convert('RGB')
            except Exception as e:
                # Catch potential errors during conversion (though 'RGB' is usually safe)
                print(f"Warning: Could not convert image to RGB: {e}. Proceeding may yield unexpected results.")
                # Depending on the error, you might want to return None here

        # Get pixel data as a flat list of RGB tuples
        pixels = list(img.getdata())
        img.close()
        return pixels, original_size

    except FileNotFoundError:
        print(f"Error: Image file not found at '{filepath}'")
        return None, None
    except UnidentifiedImageError:
        print(f"Error: Cannot identify image file. Is '{filepath}' a valid image format? (is it supported by PIL?)")
        return None, None
    except Exception as e:
        # Catch any other unexpected errors during image loading
        print(f"Error opening or reading image '{filepath}': {e}")
        return None, None

def prep_image(data_bytes, key_list, output_image_path, target_dims=None):
    # Encrypts byte data and saves it into an image file.
    print("Encrypting data with cipher (if key provided)...")
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)

    print("Converting bytes to RGB pixel data (Optimized)...")
    rgb_data = bytes_to_rgb_list(encrypted_bytes)
    required_pixels = len(rgb_data)

    width, height = 0, 0
    use_auto_resize = target_dims is None

    if use_auto_resize:
        print("Calculating optimal image size...")
        # Calculate dimensions for an approximately square image (width and height must be at least 1)
        width = max(1, math.ceil(math.sqrt(required_pixels)))
        height = max(1, math.ceil(required_pixels / width))
        print(f"Auto-calculated image size: {width}x{height}")
    else:
        width, height = target_dims
        print(f"Using specified dimensions: {width}x{height}")
        # Check if the target dimensions are sufficient
        if required_pixels > width * height:
            print(f"Error: Data ({required_pixels} pixels required) exceeds target image capacity ({width*height} pixels).")
            print("Encryption aborted. Try without preserving dimensions or use a larger image/target file.")
            return False # Indicate failure

    total_pixels = width * height
    padding_needed = total_pixels - required_pixels
    padded_rgb = rgb_data + [(0, 0, 0)] * padding_needed

    print(f"Creating image '{output_image_path}'...")
    try:
        # Creates the image and puts the data into it
        img = Image.new("RGB", (width, height))
        # putdata expects a sequence of pixel values; padded_rgb is a list of tuples.
        img.putdata(padded_rgb)
        img.save(output_image_path, format='PNG')
        img.close()
        print("Image created/updated successfully.")
        return True
    except Exception as e:
        print(f"Error creating or saving image: {e}")
        return False

# --- WAV Handling (Stereo Enabled) ---
def prep_wav(data_bytes, key_list, output_wav_path, sample_rate=44100, sample_width=2):
    # Encrypts byte data and saves it into a stereo WAV audio file.
    print("Encrypting data with cipher (if key provided)...")
    encrypted_bytes = cipher(data_bytes, key_list, encrypting=True)

    # Determine WAV parameters.
    num_channels = 2 # < This program converts files into stereo by default. Feel free to change this value to 1 for mono audio (it's not going to sound particularly pleasant either way)
    bytes_per_frame = num_channels * sample_width

    # Pad data to align with frame size (important for stereo)
    remainder = len(encrypted_bytes) % bytes_per_frame # Use bytes_per_frame
    if remainder != 0:
        padding_needed = bytes_per_frame - remainder
        encrypted_bytes += b'\x00' # Add null bytes for padding
        print(f"Padded data with {padding_needed} zero bytes for WAV frame alignment (Stereo).")

    num_frames = len(encrypted_bytes) // bytes_per_frame

    print(f"Creating stereo WAV file '{output_wav_path}'...")
    try:
        with wave.open(output_wav_path, 'wb') as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.setnframes(num_frames)
            wf.writeframes(encrypted_bytes)
        print("Stereo WAV file created successfully.")
        return True
    except wave.Error as e:
        print(f"Error writing WAV file: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during WAV creation: {e}")
        return False

def load_wav(filepath):
    # Loads a WAV file and returns its raw frame data as bytes. It works for both stereo and mono because it reads the raw bytestream.
    try:
        with wave.open(filepath, 'rb') as wf:
            # You could add checks here: wf.getnchannels(), wf.getsampwidth() etc. if needed
            print(f"Loading WAV: {wf.getnchannels()} channels, {wf.getframerate()} Hz, {wf.getsampwidth()} bytes/sample")
            frames = wf.readframes(wf.getnframes()) # Read all frames
            return frames
    except FileNotFoundError:
        print(f"Error: WAV file not found at '{filepath}'")
        return None
    except wave.Error as e:
        # This catches issues like incorrect WAV format, headers, etc.
        print(f"Error reading WAV file '{filepath}': {e}. Is it a valid WAV file?")
        return None
    except Exception as e:
        print(f"Error opening or reading WAV file '{filepath}': {e}")
        return None

# --- Core encryption/decryption Logic ---
def encrypt_file(target_data_file, output_media_path, media_type, key_str):
    # Handles encrypting the target data file into the specified media type.
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
        # Catch other potential file reading errors (e.g., permissions)
        print(f"Error reading data file: {e}")
        return

    keys = phk(key_str)

    # Prepend the original file size to the data
    try:
        # Pack the original size into bytes using the specified format (big-endian unsigned long long)
        size_bytes = struct.pack(SIZE_STRUCT_FORMAT, original_size)
    except struct.error as e:
        # This could happen if the file is too big, but unlikely with 'Q'
        print(f"Error packing file size ({original_size}): {e}. Cannot proceed.")
        return
    
    data_to_process = size_bytes + file_bytes
    success = False # Flag of success!!!

    # --- Image Encryption Path ---
    if media_type == 'png':
        print(f"Starting file encryption to {media_type.upper()}...")
        start_time = time.time()
        target_dims = None # Default to auto-calculating dimensions
        if os.path.exists(output_media_path):
            preserve = input(f"Output image '{output_media_path}' exists. Preserve its dimensions? (y/n, default = n): ").strip().lower()
            if preserve == 'y':
                print("Attempting to use existing image dimensions...")
                _, existing_dims = load_image(output_media_path)
                if existing_dims:
                    target_dims = existing_dims
                else:
                    print("Could not load existing image dimensions. Using auto-resize.")
        success = prep_image(data_to_process, keys, output_media_path, target_dims)

    # --- WAV Encryption Path ---
    elif media_type == 'wav':
        try:
            sr_str = input("Enter sample rate (e.g., 44100, default): ")
            sw_str = input("Enter sample width bytes (1 for 8-bit, 2 for 16-bit, default 2): ")
            print(f"Starting file encryption to {media_type.upper()}...")
            start_time = time.time()

            sr = int(sr_str) if sr_str else 44100
            sw = int(sw_str) if sw_str else 2

            if sw not in [1, 2]:
                raise ValueError("Sample width must be 1 or 2")
            if sr <= 0:
                raise ValueError("Sample rate must be positive")

        except ValueError as e:
            print(f"Invalid input: {e}. Using defaults (44100 Hz, 16-bit).")
            sr, sw = 44100, 2
        
        success = prep_wav(data_to_process, keys, output_media_path, sample_rate=sr, sample_width=sw)

    else:
        # If this point is reached, something has gone very wrong :(
        print(f"Error: Unknown media type '{media_type}' for encryption.")
        return

    end_time = time.time()
    if success:
        print(f"File encryption finished in {end_time - start_time:.4f} seconds.")
    else:
        print("File encryption failed.")


def decrypt_file(input_media_path, media_type, key_str, output_filepath):
    # Handles decrypting a file from the specified media type.
    if not output_filepath:
        print("Output filename cannot be empty. Aborting decryption.")
        return

    print(f"Attempting decryption from {media_type.upper()} '{input_media_path}' to new file '{output_filepath}'...")
    start_time = time.time()

    keys = phk(key_str)

    # 1. Get raw byte data from the media file
    raw_data_bytes = None
    if media_type == 'png':
        pixels, _ = load_image(input_media_path)
        if pixels is None:
            print("File decryption failed (could not load image pixels).")
            return
        print("Converting pixels to byte stream (Optimized)...")

        raw_data_bytes = rgb_list_to_bytes(pixels)

    elif media_type == 'wav':
        raw_data_bytes = load_wav(input_media_path)
        if raw_data_bytes is None:
            print("File decryption failed (could not load WAV data).")
            return

    else:
        # This point shouldn't be reached if everything is working correctly.
        # If you somehow get here, say hi to me through pulling an issue request in GitHub :)
        print(f"Error: Unknown media type '{media_type}' for decryption.")
        return

    # Check if data extraction was successful
    if not raw_data_bytes:
        print("Error: Failed to extract raw byte data from the media file.")
        return

    # 2. Decrypt the raw byte stream
    print("Decrypting byte stream with cipher (if key provided)...")
    all_decrypted_bytes = cipher(raw_data_bytes, keys, encrypting=False)

    # 3. Extract original file size and data (and check if the decrypted data is long enough to contain the size header)
    if len(all_decrypted_bytes) < SIZE_BYTES_LEN:
        print(f"Error: Decrypted data stream is too short ({len(all_decrypted_bytes)} bytes) to contain file size info ({SIZE_BYTES_LEN} bytes).")
        print(" Possible reasons: incorrect key, corrupted file, file not created by this program, or incorrect media type selected.")
        return

    print("Extracting original file size and data...")
    try:
        # Slice the first bytes for the size header
        size_bytes = all_decrypted_bytes[:SIZE_BYTES_LEN]
        # Unpack the size bytes back into an integer
        original_size = struct.unpack(SIZE_STRUCT_FORMAT, size_bytes)[0]
        print(f"Extracted original file size: {original_size} bytes.")

        # Slice the remaining bytes as the original file data
        extracted_file_data = all_decrypted_bytes[SIZE_BYTES_LEN:]

        # 4. Truncate data to the original size (removing any padding added during encryption, like for WAV alignment or image pixel padding)
        if len(extracted_file_data) < original_size:
            print(f"Warning: Actual data length ({len(extracted_file_data)}) is less than expected original size ({original_size}).")
            print("File might be incomplete or corrupted.")
            # Use all the data available in this case
            final_file_data = extracted_file_data
        else:
            # Truncate the extracted data to the original file size
            final_file_data = extracted_file_data[:original_size]

    except struct.error as e:
        print(f"Error unpacking file size: {e}. Media file data may be corrupted, the key might be wrong, or it's not an Opaline file.")
        return
    except Exception as e:
        # uh oh :(
        print(f"An unexpected error occurred during data extraction: {e}")
        return

    # 5. Write the decrypted data to the output file
    print(f"Attempting to write {len(final_file_data)} bytes to new file '{output_filepath}'...")
    try:
        # Open the output file in binary write mode
        with open(output_filepath, 'wb') as f:
            f.write(final_file_data)
        end_time = time.time()
        print(f"Finished writing decrypted data to '{output_filepath}' in {end_time - start_time:.4f} seconds.")
    except Exception as e:
        end_time = time.time()
        print(f"Error writing decrypted file '{output_filepath}': {e}")


# --- File Selection ---
def select_target_file():
    # Opens a file dialog for the user to select a target file.
    print("\nPlease select the target file (file to encrypt or media file to decrypt)...")

    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    selected_path = filedialog.askopenfilename(
        title="Select Target File"
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
    # Clears the screen and displays the main menu options.
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
    # Main execution loop for the program.
    target_file = None # Variable to store the path of the selected target file
    # Default filenames (feel free to change these at the beginning of the program, if you're reading this)
    png_path_default = DEFAULT_PNG_FILENAME
    wav_path_default = DEFAULT_WAV_FILENAME

    while True:
        display_ui(target_file)
        choice = input("Enter choice (1-4): ")

        try:
            n = int(choice)
            os.system('cls' if os.name == 'nt' else 'clear')

            # --- Option 1: Select target ---
            if n == 1:
                selected = select_target_file()
                if selected:
                    target_file = selected

            # --- Option 2: Encrypt target ---
            elif n == 2:
                if not target_file:
                    print("Error: No target file selected.")
                    print("Please use option 1 first to select the file you want to encrypt.")
                    input("\nPress Enter to continue...")
                    continue

                # Prompt for output format
                print("-" * 60)
                print("Choose an output format: ")
                print("  1. Image (png)")
                print("  2. Audio (wav)")
                print("  3. Back")
                print("-" * 60)

                media_choice_str = input("Choose output format (default = image): ")
                media_choice = 1
                if media_choice_str:
                    try:
                        media_choice = int(media_choice_str)
                    except ValueError:
                        print("\nInvalid choice. Defaulting to image.")
                        media_choice = 1
                else:
                     media_choice = 1

                output_media_path = ""
                media_type = ""

                # --- Encrypt to PNG ---
                if media_choice == 1:
                    media_type = 'png'
                    output_media_path = input(
                        f"Enter output PNG filename (blank uses '{png_path_default}'): ").strip() or png_path_default
                # --- Encrypt to WAV ---
                elif media_choice == 2:
                    media_type = 'wav'
                    output_media_path = input(
                        f"Enter output WAV filename (blank uses '{wav_path_default}'): ").strip() or wav_path_default
                elif media_choice == 3:
                    continue
                # --- Invalid sub-option ---
                else:
                     print("\nInvalid format choice. Returning to main menu.")
                     input("\nPress Enter to continue...")
                     continue

                key = input("Enter optional encryption key (hex values separated by spaces, e.g., '1F A0 33'), or leave blank for no encryption: ").strip()
                encrypt_file(target_file, output_media_path, media_type, key)
                input("\nPress Enter to continue...")

            # --- Option 3: Decrypt Target Media File ---
            elif n == 3:
                 # Check if a target file (the media file to decrypt) has been selected
                if not target_file:
                    print("Error: No target file selected.")
                    print("Please use option 1 first to select the .png or .wav file you want to decrypt.")
                    input("\nPress Enter to continue...")
                    continue

                # Determine media type from file extension
                _, ext = os.path.splitext(target_file)
                ext = ext.lower()[1:]
                if ext in ['png', 'wav']:
                    media_type = ext
                else:
                    print(f"Error: Cannot determine supported media type from extension '{ext}'.")
                    print(" Please select a png or wav file that you know was created by Opaline.")
                    input("\nPress Enter to continue...")
                    continue

                key = input("Enter optional decryption key used during encryption (hex values separated by spaces), or leave blank if no key was used: ").strip()
                print("\nThis next step is important. You must enter the a file name and the correct file extension.")
                out_file = input(
                    "Enter desired filename for the decrypted file (e.g., 'document.txt', 'archive.zip'): ").strip()

                if not out_file:
                    print("\nNo output filename provided. Decryption cancelled.")
                else:
                    decrypt_file(target_file, media_type, key, out_file)
                input("\nPress Enter to continue...")

            # --- Option 4: Exit ---
            elif n == 4:
                print("Exiting Opaline. Goodbye! :)")
                break   

            else:
                print(f"\nInvalid choice ({n}). Please enter a number between 1 and 4.")
                input("\nPress Enter to continue...")

        # --- ValueError ---
        except ValueError:
            print("\nInvalid input. Please enter a number (1-4).")
            input("Press Enter to continue...") # Pause for user to read message

        # --- Exit key is Control + C (good to remember if something goes wrong) ---
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user (Ctrl+C). Exiting.")
            break

        # --- Catch-all for other unexpected errors ---
        except Exception as e:
            print(f"\nAn unexpected error occurred in the main loop: {e}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

# --- By Alex Hall :) ---
if __name__ == "__main__":
    main()
