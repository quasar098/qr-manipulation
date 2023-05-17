from PIL.Image import Image, open as open_image
import argparse


def round_to_color(col: tuple[int, int, int]) -> int:
    if col[0] < 128 and col[1] < 128 and col[2] < 128:
        return 0
    return 1


def binary_repr(num: int):
    return bin(num)


def decode_img(img: Image):

    # remove excess pixels from image
    pixel_map = {}
    assert img.width == img.height, "Image is not square"
    for x in range(img.width):
        for y in range(img.height):
            pixel_map[(x, y)] = img.getpixel((x, y))
    for _ in range(min(img.width, img.height)):
        diag_coord = (_, _)
        if round_to_color(pixel_map[diag_coord]) == 0:
            img = img.crop((_, _, img.width, img.height))
            break
    for _ in range(min(img.width, img.height), -1, -1):
        diag_coord = (_, _)
        if round_to_color(pixel_map[diag_coord]) == 0:
            img = img.crop((0, 0, _-3, _-3))
            break
    assert img.height == img.width, "QR Code is not square?? What"

    # calculate qr code version and size
    version = int((img.height-17)/4)
    assert 1 <= version <= 40, f"Invalid QR Code Version: {version}"
    print(f"QR Code Size: {img.width}x{img.height}\nQR Code Version: {version}")

    # calculate mask and compression info
    format_image = img.crop((0, 8, 5, 9))
    chunks1 = [round_to_color(format_image.getpixel((_, 0))) for _ in range(0, 5)]
    total = 0
    for chunk1 in chunks1:
        total += chunk1 ^ 1
        total = total << 1
    total = total >> 1
    total = total ^ 0b10101
    compression_code_in_decimal = (total & 0b11000) >> 3
    compression_lvl = {0: "M", 1: "L", 2: "H", 3: "Q"}
    print(f"Compression Level: {compression_lvl[compression_code_in_decimal]}")
    qr_mask_num = total & 0b111
    formatted_mask = str(binary_repr(qr_mask_num))[2:].rjust(3, '0')
    print(f"Mask Pattern: {formatted_mask}")
    mask_equation = {
        0: "(row + column) mod 2 == 0",
        1: "(row) mod 2 == 0",
        2: "(column) mod 3 == 0",
        3: "(row + column) mod 3 == 0",
        4: "(floor(row / 2) + floor(column / 3)) mod 2 == 0",
        5: "((row * column) mod 2) + ((row * column) mod 3) == 0",
        6: "(((row * column) mod 2) + ((row * column) mod 3)) mod 2 == 0",
        7: "(((row + column) mod 2) + ((row * column) mod 3)) mod 2 == 0"
    }.get(qr_mask_num)
    assert 0 <= qr_mask_num <= 7, f"QR Mask Pattern Invalid Number: {qr_mask_num} ({formatted_mask})"
    print(f"Mask Equation: {mask_equation}")

    # mask the stuff
    assert version < 7, "Decoding for versions >= 7 not built in yet"
    # todo do this


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("infile")
    namespace = parser.parse_args()

    infile = namespace.infile

    with open_image(infile) as opened:
        decode_img(opened)


if __name__ == '__main__':
    main()
