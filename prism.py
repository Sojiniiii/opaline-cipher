import os
import math
import time
from PIL import Image

def phc():
    try:
        img = Image.open("img.png")
    except FileNotFoundError:
        print("Image file not found")
        return
    except Exception as e:
        print(f"Error opening image: {e}")
        return
    return list(img.getdata())

def pkey(key):
    if not key.strip():
        return []
    parts = key.split(' ')
    keys = []
    for part in parts:
        part = part.strip()
        keys.append(int(part, 16))
    return keys

def encrypt(rgb, key=""):
    img = Image.open("img.png")
    h, w = img.size
    img.close()
    img = Image.new("RGB", (h, w), (0, 0, 0))
    pixels = list(img.getdata())
    keys = pkey(key)
    index = 0
    for i in range(len(pixels)):
        if index < len(rgb):
            pixel = rgb[index]
            index += 1
            if keys and pixel != (0, 0, 0):
                new_pixel = tuple((channel + keys[j % len(keys)]) % 256 for j, channel in enumerate(pixel[:3]))
                pixels[i] = new_pixel
            else:
                pixels[i] = pixel
        else:
            break
    
    img.putdata(pixels)
    img.save("img.png")
    print("Image modified and saved")

def decrypt(key=""):
    pixels = phc()
    if pixels is None:
        return None
    keys = pkey(key)
    if keys is None:
        return None
    if keys:
        new_pixels = []
        for pixel in pixels:
            if pixel != (0, 0, 0):
                new_pixel = tuple((channel - keys[j % len(keys)]) % 256 for j, channel in enumerate(pixel[:3]))
                new_pixels.append(new_pixel)
            else:
                new_pixels.append(pixel)
        return new_pixels
    else:
        return pixels

def rgb_to_hex(rgb):
    if isinstance(rgb, (tuple, list)) and len(rgb) >= 3:
        r, g, b = rgb[:3]
    else:
        print("Invalid RGB value; must be a tuple or list with at least 3 values.")
        return None
    if not all(isinstance(x, int) and 0 <= x <= 255 for x in (r, g, b)):
        print("RGB values must be integers between 0 and 255.")
        return None

    return '%02x%02x%02x' % (r, g, b)

def hex_to_rgb(hex_str):
    hex_str = hex_str.strip("#")
    if not hex_str:
        return None
    rgb = []
    for x in range(0, len(hex_str), 6):
        hex_chunk = hex_str[x:x + 6]
        while len(hex_chunk) < 6:
            hex_chunk += "0"
        red = int(hex_chunk[0:2], 16)
        green = int(hex_chunk[2:4], 16)
        blue = int(hex_chunk[4:6], 16)
        rgb.append((red, green, blue))
    return rgb

if not os.path.exists("img.png"):
    img = Image.new("RGB", (256, 256), (0, 0, 0))
    img.save("img.png")

if not os.path.exists("input.txt"):
    with open("input.txt", 'w'):
        pass

if not os.path.exists("text.txt"):
    with open("text.txt", 'w'):
        pass

while True:
    print("Prism Cipher by Alex Hall")
    print("\n1. Encrypt Text\n2. Decrypt Image\n3. Make Image File\n4. Exit\n")
    operation = input()
    try:
        n = int(operation)
        if n > 0 and n < 5:
            break
        else:
            print("\nInvalid input\n")
    except:
        print("\nInvalid input\n")

operation = int(operation)

if operation == 1:
    text = input("What text would you like to encode? Leave blank to use the text file.\n")
    if not text:
        with open("input.txt") as f:
            text = f.read()
    key = input("\nEnter 1-3 hexadecimal values (separated by spaces), or leave blank for no cipher: ")
    print("Loading...")
    start_time = time.time()
    text_rgb = hex_to_rgb(text.encode('utf-8').hex())
    encrypt(text_rgb, key)
    end_time = time.time()
    print("Finished creating image in " + str(end_time - start_time) + " seconds.")
elif operation == 2:
    key = input("\nEnter 1-3 hexadecimal values (separated by spaces), or leave blank for no cipher: ")
    print("Loading...")
    start_time = time.time()
    color_map = decrypt(key)
    for x in range(len(color_map)):
        color_map[x] = rgb_to_hex(color_map[x])
    color_map = ''.join(color_map)
    text_output = ''.join([chr(int(color_map[i:i+2], 16)) for i in range(0, len(color_map), 2)])
    with open("text.txt", "w") as file:
        file.write(text_output)
    end_time = time.time()
    print("Finished writing to file in " + str(end_time - start_time) + " seconds")
elif operation == 3:
    while True:
        try:
            print("WARNING: This will erase your current image file!")
            square = int(input("What should the width and height of the square be? (leave blank for standard 256x256): "))
            if square > 2048:
                print("The size of the square is too big!")
            elif square < 0:
                print("The size of the square cannot be less than 0!")
                break
            else:
                break
        except:
            square = 256
            break
    
    img = Image.new("RGB", (square, square), (0, 0, 0))
    img.save("img.png")
    print("New square created!")
elif operation == 4:
    quit(1)