from PIL.Image import Image, open as open_image
import argparse
from math import floor

import data


def round_to_color(col: tuple[int, int, int]) -> int:
    if col[0] < 128 and col[1] < 128 and col[2] < 128:
        return 0
    return 1


def expand_from_bool(ball: int) -> tuple[int, int, int]:
    if ball == 0:
        return 0, 0, 0
    return 255, 255, 255


def binary_repr(num: int):
    return bin(num)


def decode_img(img: Image):

    # remove excess pixels from image
    pixel_map = {}
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
    print(f"Mask Equation: Flip bit if {mask_equation}")

    # mask the stuff
    assert version < 7, "Decoding for versions >= 7 not built in yet"
    encoding_meanings = [
        "0000, End of message (Terminator)",
        "0001, Numeric encoding (10 bits per 3 digits)",
        "0010, Alphanumeric encoding (11 bits per 2 characters)",
        "0011, Structured append (used to split a message across multiple QR symbols)",
        "0100, UTF-8 encoding (8 bits per character)",
        "0101, FNC1 in first position (see Code 128 for more information)",
        "0110, INVALID!"
        "0111, Extended Channel Interpretation (select alternate character set or encoding)",
        "1000, Kanji encoding (13 bits per character)",
        "1001, FNC1 in second position",
        "1010, INVALID",
        "1011, INVALID",
        "1100, INVALID",
        "1101, INVALID",
        "1110, INVALID",
        "1111, INVALID",
    ]
    img = maskify(img, qr_mask_num)
    encoding_type = 0
    for yoffset in range(1, 3):
        for xoffset in range(1, 3):
            encoding_type = (encoding_type << 1) ^ (1-round_to_color(img.getpixel((img.width-xoffset, img.height-yoffset))))
    print(f"Information type bits: {encoding_meanings[encoding_type].split(', ')[0]}")
    print(f"Information type meaning: {encoding_meanings[encoding_type].split(', ')[1]}")
    expected_holding = []
    groups = ["Numeric", "Alphanumeric", "UTF-8", "Kanji"]
    index = 0
    for _ in range(compression_code_in_decimal ^ 1, 16, 4):
        expected_holding.append(f"{groups[index]} encoding capacity: {str(data.qr_holding_info[version][_])} bytes")
        index += 1
    for expect in expected_holding:
        print(expect)

    start_x, start_y = img.width-1, img.height-1
    times = 0
    going_up = True
    bits = []
    pair = []
    while start_x != -2:
        if start_y < 0:
            going_up = False
            start_y = 0
            start_x -= 3
        if start_y >= img.height:
            going_up = True
            start_y = img.height-1
            start_x -= 1

        # calculate stuff
        bit = 1-round_to_color(img.getpixel((start_x, start_y)))
        if position_is_good(img, start_x, start_y):
            highlighter(img, (start_x, start_y))
            pair.append(bit)
            if len(pair) == 2:
                if not going_up:
                    pair.reverse()
                bits.extend(pair)
                pair = []

        # move start_x and start_y
        if going_up:
            start_x -= 1
            if start_x % 2 == 0:
                start_x += 2
                start_y -= 1
        else:
            start_x += 1
            if start_x % 2 != 0:
                start_x -= 2
                start_y += 1
        times += 1
    added_map = {
        0b0001: 10,
        0b0010: 9,
        0b0100: 8,
        0b1000: 8
    }
    length_list = bits[4:4+added_map.get(encoding_type, 0)]

    def sum_of_bits(bits_, num_bits=8):
        return sum([value*(2**((num_bits-1)-index2)) for index2, value in enumerate(bits_)])

    length_of_info = sum_of_bits(length_list, added_map.get(encoding_type, 0))
    print(f"Length of Data: {length_of_info, length_list}")
    if encoding_type == 0b0100:  # utf-8
        encoded_information_bits = bits[12:12+8*length_of_info]
        encoded_information_list = [sum_of_bits(chunk) for chunk in
                                    [encoded_information_bits[_*8:(_+1)*8] for _ in range(
                                        len(encoded_information_bits)//8)]]
        print(f'Data in hex: {"".join(hex(sum_of_bits(encoded_information_bits, len(encoded_information_bits))))}')
        print(f'Actual data: {"".join([chr(_3) for  _3 in encoded_information_list])}')
    if encoding_type == 0b0010:  # alphanumeric
        pass
    img.show()


def highlighter(img: Image, pos: tuple[int, int]):
    x, y = pos
    prev = round_to_color(img.getpixel((x, y)))
    if not prev:
        img.putpixel((x, y), (255, 128, 128))
    else:
        img.putpixel((x, y), (128, 255, 128))


def position_is_good(img, x_, y_):
    w = img.width
    h = img.height
    if x_ < 0 or y_ < 0:
        return False
    if x_ <= 8 and y_ <= 8:
        return False
    if w-x_ <= 8 and y_ <= 8:
        return False
    if x_ <= 8 and h-y_ <= 8:
        return False
    if x_ == 6:
        return False
    if y_ == 6:
        return False
    if img.width != 21:
        if 5 <= w-x_ <= 9 and 5 <= h-y_ <= 9:
            return False
    if x_ == 8 and h-y_ == 8:
        return False
    return True


def maskify(img: Image, mask_n: int) -> Image:

    mask_lambda = {
        0: lambda row, column: (row + column) % 2 == 0,
        1: lambda row, column: row % 2 == 0,
        2: lambda row, column: column % 3 == 0,
        3: lambda row, column: (row + column) % 3 == 0,
        4: lambda row, column: (floor(row / 2) + floor(column / 3)) % 2 == 0,
        5: lambda row, column: ((row * column) % 2) + ((row * column) % 3) == 0,
        6: lambda row, column: (((row * column) % 2) + ((row * column) % 3)) % 2 == 0,
        7: lambda row, column: (((row + column) % 2) + ((row * column) % 3)) % 2 == 0
    }
    for x in range(img.width):
        for y in range(img.height):
            old = round_to_color(img.getpixel((x, y)))
            if position_is_good(img, x, y):
                if mask_lambda[mask_n](x, y):
                    old = 1-old
            img.putpixel((x, y), expand_from_bool(old))
    return img


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("infile")
    namespace = parser.parse_args()

    infile = namespace.infile

    with open_image(infile) as opened:
        decode_img(opened)


if __name__ == '__main__':
    main()
