import os
import math
import time
import struct
from tkinter import filedialog, Tk
from PIL import Image, UnidentifiedImageError

# --- Configuration ---
DEFAULT_IMAGE_FILENAME = "image.png"

# --- Key functions ---
def phk(key_str):
    """Parses a string of hexadecimal values into a list of integers. PHK stands for Parse Hex Key."""
    if not key_str: return []
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

# --- Conversion functions ---
def rgb_to_hex(rgb):
    if not isinstance(rgb, (tuple, list)) or len(rgb) < 3:
        return "000000"
    try:
        r, g, b = [max(0, min(255, int(x))) for x in rgb[:3]]
        return f'{r:02x}{g:02x}{b:02x}'
    except (ValueError, TypeError):
        return "000000"

def hex_to_rgb(hex_chunk):
    hex_chunk = hex_chunk.ljust(6, '0')
    try:
        r = int(hex_chunk[0:2], 16)
        g = int(hex_chunk[2:4], 16)
        b = int(hex_chunk[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (0, 0, 0)

def bytes_to_rgb(data_bytes):
    hex_data = data_bytes.hex()
    rgb_list = []
    for i in range(0, len(hex_data), 6):
        hex_chunk = hex_data[i:i+6]
        rgb_list.append(hex_to_rgb(hex_chunk))
    return rgb_list

def rgb_list_to_bytes(rgb_list):
    hex_list = [rgb_to_hex(rgb) for rgb in rgb_list]
    hex_string = "".join(hex_list)
    try:
        return bytes.fromhex(hex_string)
    except ValueError as e:
        print(f"Error converting final hex string to bytes: {e}. Data likely corrupted.")
        return b''

# --- Encryption logic ---
def cipher(rgb_list, keys, encrypting=True):
    """Encrypts or decrypts a list of RGB tuples using a list of keys."""
    if not keys: return rgb_list
    processed_pixels = []
    key_len = len(keys)
    op = (lambda a, b: (a + b) % 256) if encrypting else (lambda a, b: (a - b) % 256)
    for pixel in rgb_list:
        if isinstance(pixel, (tuple, list)) and len(pixel) >= 3 and all(isinstance(x, int) and 0 <= x <= 255 for x in pixel[:3]):
            r, g, b = pixel[:3]
            new_pixel = tuple(op(channel, keys[j % key_len]) for j, channel in enumerate((r, g, b)))
            processed_pixels.append(new_pixel)
        else:
            processed_pixels.append(pixel)
    return processed_pixels

def load(filepath):
    """Loads an image file and returns its pixel data."""
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

def prep(data_bytes, key_list, output_image_path, target_dims=None):
    """Encrypts byte data into an image file."""
    print("Preparing data and applying cipher...")
    rgb_data = bytes_to_rgb(data_bytes)
    encrypted_rgb = cipher(rgb_data, key_list, encrypting=True)
    required_pixels = len(encrypted_rgb)

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
    padded_rgb = encrypted_rgb + [(0, 0, 0)] * padding_needed

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

# --- Mode handlers ---
def encrypt(target_data_file, default_img_path):
    """Handles encrypting the target data file into an image."""
    if not target_data_file:
        print("Error: No target data file selected for encryption input. Use option 4 first.")
        return

    input_filepath = target_data_file
    print(f"Attempting to encrypt data file: {input_filepath}")

    try:
        with open(input_filepath, 'rb') as f:
            file_bytes = f.read()
        original_size = len(file_bytes)
        print(f"Read {original_size} bytes from the file.")
    except FileNotFoundError:
        print(f"Error: Target data file '{input_filepath}' not found.")
        return
    except Exception as e:
        print(f"Error reading data file: {e}")
        return

    keys = input("\nEnter optional encryption key (hex values separated by spaces, like 'ff 1a 3b'), or leave blank for no cipher: ").strip()
    keys = phk(keys)
    output_image_path = input(f"Enter output IMAGE filename (e.g., 'secret.png', blank uses '{default_img_path}'): ").strip() or default_img_path

    target_dims = None
    if os.path.exists(output_image_path):
        preserve = input(f"Output image '{output_image_path}' exists. Preserve its dimensions? (y/n, default n): ").strip().lower()
        if preserve == 'y':
            print("Attempting to use existing image dimensions...")
            _, existing_dims = load(output_image_path)
            if existing_dims:
                target_dims = existing_dims
            else:
                print("Could not load existing image dimensions. Using auto-resize.")

    size_struct_format = '>Q'
    try:
        size_bytes = struct.pack(size_struct_format, original_size)
    except struct.error as e:
         print(f"Error packing file size ({original_size}): {e}. Cannot proceed.")
         return

    data_to_encrypt = size_bytes + file_bytes

    print("Starting file encryption...")
    start_time = time.time()
    success = prep(data_to_encrypt, keys, output_image_path, target_dims)
    end_time = time.time()

    if success:
        print(f"File encryption finished in {end_time - start_time:.4f} seconds.")
    else:
        print("File encryption failed.")


def decrypt(default_img_path):
    """Handles decrypting a file from an image, prompting for a new output filename."""

    input_image_path = input(f"Enter image filename to decrypt (blank uses '{default_img_path}'): ").strip() or default_img_path
    keys = input("\nEnter optional encryption key (hex values separated by spaces, like 'ff 1a 3b'), or leave blank for no cipher: ").strip()
    keys = phk(keys)

    output_filepath = input("Enter the desired filename for the new decrypted file (e.g., 'text.txt', 'archive.zip'): ").strip()
    if not output_filepath:
        print("Output filename cannot be empty. Aborting decryption.")
        return

    print(f"Attempting decryption from '{input_image_path}' to new file '{output_filepath}'...")
    start_time = time.time()

    # 1. Load pixels
    pixels, _ = load(input_image_path)
    if pixels is None:
        print("File decryption failed (could not load image pixels).")
        return

    # 2. Decrypt pixels
    decrypted_pixels = cipher(pixels, keys, encrypting=False)

    # 3. Convert to bytes
    print("Converting pixels to byte stream...")
    all_decrypted_bytes = rgb_list_to_bytes(decrypted_pixels)
    if not all_decrypted_bytes:
         print("Error: Failed to convert pixels back to bytes. Decryption aborted.")
         return

    # 4. Extract size
    size_struct_format = '>Q'
    size_bytes_len = struct.calcsize(size_struct_format)

    if len(all_decrypted_bytes) < size_bytes_len:
        print(f"Error: Decrypted data stream is too short ({len(all_decrypted_bytes)} bytes) for file size info ({size_bytes_len} bytes).")
        return

    print("Extracting file size and data...")
    try:
        size_bytes = all_decrypted_bytes[:size_bytes_len]
        original_size = struct.unpack(size_struct_format, size_bytes)[0]
        print(f"Extracted original file size: {original_size} bytes.")

        # 5. Extract data
        raw_file_data = all_decrypted_bytes[size_bytes_len:]

        # 6. Truncate data
        if len(raw_file_data) < original_size:
             print(f"Warning: Actual data length ({len(raw_file_data)}) is less than expected size ({original_size}). File might be incomplete or corrupted.")
             file_data = raw_file_data
        else:
            file_data = raw_file_data[:original_size]

    except struct.error as e:
        print(f"Error unpacking file size: {e}. Image data may be corrupted or key is wrong.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data extraction: {e}")
        return

    print(f"Attempting to write {len(file_data)} bytes to new file '{output_filepath}'...")
    try:
        with open(output_filepath, 'wb') as f:
            f.write(file_data)
        end_time = time.time()
        print(f"Finished writing decrypted data to '{output_filepath}' in {end_time - start_time:.4f} seconds.")
        print("REMINDER: Ensure the filename has the correct extension to open it.")
    except Exception as e:
        end_time = time.time()
        print(f"Error writing decrypted file '{output_filepath}': {e}")


def make_image(default_img_path):
    """Creates a new blank (black) image file, overwriting the default path."""
    print(f"\nWARNING: This will overwrite '{default_img_path}'!")
    print("Enter dimensions for the new image.")
    while True:
        dims_input = input("Either enter width and height (separated by spaces), width alone, or blank for default (256x256): ").strip()
        max_dim = 4096
        try:
            if not dims_input: width, height = 256, 256
            else:
                parts = dims_input.split()
                if len(parts) == 1: width = height = int(parts[0])
                elif len(parts) == 2: width, height = int(parts[0]), int(parts[1])
                else: print("Invalid format."); continue
            if not (0 < width <= max_dim and 0 < height <= max_dim):
                print(f"Dimensions must be between 1 and {max_dim}."); continue
            break
        except ValueError: print("Invalid numbers.")
        except Exception as e: print(f"Error: {e}"); continue

    try:
        img = Image.new("RGB", (width, height), (0, 0, 0))
        img.save(default_img_path, format='PNG')
        img.close()
        print(f"New blank image '{default_img_path}' ({width}x{height}) created!")
    except Exception as e:
        print(f"Error creating image file: {e}")

def selfile():
    """Allows user to select the target data file path (for ENCRYPTION INPUT)."""
    print("Please select the target file (for encryption)")

    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected_path = filedialog.askopenfilename(
        title="Select target"
    )
    root.destroy()

    if selected_path:
        print(f"\nTarget set to: {selected_path}")
        return selected_path
    else:
        print("\nNo file selected; target remains unset.")
        return None

# --- user interface ---
def ui(target_data_file, default_img):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("-=- Opaline by Alex Hall -=-")
    print(f"Target file: {target_data_file if target_data_file else 'Not Set'}")
    print(f"Default image file: {default_img}")
    print("\nChoose an operation:")
    print("  1. Encrypt target")
    print("  2. Decrypt image")
    print("  3. Select target")
    print("  4. Create new image")
    print("  5. Exit")

def main():
    target = None
    path = DEFAULT_IMAGE_FILENAME

    while True:
        ui(target, path)
        choice = input("Enter choice (1-5): ")

        try:
            n = int(choice)
            os.system('cls' if os.name == 'nt' else 'clear')
            if n == 1:
                encrypt(target, path)
            elif n == 2:
                decrypt(path)
            elif n == 3:
                selected = selfile()
                if selected:
                    target = selected
            elif n == 4:
                make_image(path)
            elif n == 5:
                break
            else:
                print("\nInvalid choice. Please enter a number between 1 and 5.")

            input("\nPress Enter to continue...")

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
