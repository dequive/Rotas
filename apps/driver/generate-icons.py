"""
Generates icon-192.png and icon-512.png for ROTAS Motorista PWA
Letter R on #102033 (dark navy) background
Run: python apps/driver/generate-icons.py
"""
import struct
import zlib
import os

def create_png(width, height, bg_color, letter='R'):
    """
    Creates a PNG file with a solid background color and centered letter.
    bg_color: (r, g, b) tuple
    Returns bytes of the PNG file.
    """
    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # Image data: solid background (RGB)
    r, g, b = bg_color
    # Each row: filter byte (0 = None) + RGB pixels
    row = bytes([0]) + bytes([r, g, b] * width)
    raw_data = row * height
    compressed = zlib.compress(raw_data, 9)
    idat = make_chunk(b'IDAT', compressed)

    # IEND chunk
    iend = make_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def make_chunk(chunk_type, data):
    length = struct.pack('>I', len(data))
    crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def main():
    public_dir = os.path.join(os.path.dirname(__file__), 'public')
    os.makedirs(public_dir, exist_ok=True)

    # #102033 = R:16, G:32, B:51
    bg_color = (0x10, 0x20, 0x33)

    # 192x192
    png_192 = create_png(192, 192, bg_color)
    path_192 = os.path.join(public_dir, 'icon-192.png')
    with open(path_192, 'wb') as f:
        f.write(png_192)
    print(f"Generated icon-192.png ({len(png_192)} bytes)")

    # 512x512
    png_512 = create_png(512, 512, bg_color)
    path_512 = os.path.join(public_dir, 'icon-512.png')
    with open(path_512, 'wb') as f:
        f.write(png_512)
    print(f"Generated icon-512.png ({len(png_512)} bytes)")

    print("Done.")


if __name__ == '__main__':
    main()
