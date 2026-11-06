# -*- coding: utf-8 -*-
"""Nelko P21 barkod baskısı. Telefon uygulamasından bağımsız."""

from __future__ import annotations

import re
import time
from pathlib import Path
HEAD_DOTS = 96
DEFAULT_LABEL = (14, 40, 5)
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
)


def find_nelko_port(preferred: str = "") -> str:
    from serial.tools import list_ports

    spp_uuid = "00001101-0000-1000-8000-00805F9B34FB"
    ports = list(list_ports.comports())

    def outgoing(port) -> bool:
        hwid = (port.hwid or "").upper()
        if spp_uuid not in hwid and "BTHENUM" not in hwid:
            return False
        # Gelen kutu (MAC sıfır) yazıcıya bağlanmaz, hemen düşer.
        return "000000000000" not in hwid

    outgoing_ports = [port for port in ports if outgoing(port)]
    if preferred:
        for port in outgoing_ports:
            if port.device.upper() == preferred.upper():
                return port.device
    named = [
        port.device
        for port in outgoing_ports
        if "nelko" in f"{port.description} {port.hwid}".lower() or "p21" in f"{port.description} {port.hwid}".lower()
    ]
    if named:
        return named[0]
    if outgoing_ports:
        return outgoing_ports[0].device
    return ""


def parse_label_roll(block: bytes) -> tuple[int, int, int] | None:
    if len(block) != 16:
        return None
    tag_format = block[3] >> 4
    width = block[13]
    length = block[11]
    gap = block[8] if tag_format >= 2 and block[8] else 5
    if not (8 <= width <= 20 and 15 <= length <= 80):
        return None
    return int(width), int(length), int(gap)


def label_dots(width_mm: int, length_mm: int, dpi: int = 203) -> tuple[int, int]:
    width = min(HEAD_DOTS, int(round(width_mm / 25.4 * dpi)) // 8 * 8)
    height = max(80, int(round(length_mm / 25.4 * dpi)))
    return width, height


def _font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_size(draw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _fit_font(draw, text: str, max_width: int, max_height: int):
    size = max(8, max_height)
    while size > 8:
        font = _font(size)
        width, height = _text_size(draw, text, font)
        if width <= max_width and height <= max_height:
            return font
        size -= 1
    return _font(8)


CODE128 = (
    "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
    "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
    "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
    "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
    "11001001110", "11011100100", "11001110100", "11101101110", "11101001100",
    "11100101100", "11100100110", "11101100100", "11100110100", "11100110010",
    "11011011000", "11011000110", "11000110110", "10100011000", "10001011000",
    "10001000110", "10110001000", "10001101000", "10001100010", "11010001000",
    "11000101000", "11000100010", "10110111000", "10110001110", "10001101110",
    "10111011000", "10111000110", "10001110110", "11101110110", "11010001110",
    "11000101110", "11011101000", "11011100010", "11011101110", "11101011000",
    "11101000110", "11100010110", "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010", "10100110000", "10100001100",
    "10010110000", "10010000110", "10000101100", "10000100110", "10110010000",
    "10110000100", "10011010000", "10011000010", "10000110100", "10000110010",
    "11000010010", "11001010000", "11110111010", "11000010100", "10001111010",
    "10100111100", "10010111100", "10010011110", "10111100100", "10011110100",
    "10011110010", "11110100100", "11110010100", "11110010010", "11011011110",
    "11011110110", "11110110110", "10101111000", "10100011110", "10001011110",
    "10111101000", "10111100010", "11110101000", "11110100010", "10111011110",
    "10111101110", "11101011110", "11110101110", "11010000100", "11010010000",
    "11010011100",
)
CODE128_STOP = "1100011101011"


def _code128_bits(values: list[int]) -> str:
    checksum = values[0]
    for position, value in enumerate(values[1:], start=1):
        checksum += position * value
    values.append(checksum % 103)
    return "".join(CODE128[value] for value in values) + CODE128_STOP


def code128_modules(text: str) -> str:
    """Rakamsa sıkışık Code C, diğer yazılarda Code B."""
    text = str(text).strip()
    if text.isdigit():
        values = [105]
        index = 0
        while index + 1 < len(text):
            values.append(int(text[index : index + 2]))
            index += 2
        if index < len(text):
            values.append(100)
            values.append(ord(text[index]) - 32)
        return _code128_bits(values)
    values = [104]
    for char in text:
        code = ord(char)
        if code < 32 or code > 126:
            code = ord("?")
        values.append(code - 32)
    return _code128_bits(values)


def render_barcode_bitmap(text: str, width: int, height: int, caption: str | None = None) -> bytes:
    """Uzun kenarda Code 128, yanında yazı. 0 biti siyah basar."""
    from PIL import Image, ImageDraw

    shown = (caption if caption is not None else str(text)).strip()
    page = Image.new("1", (width, height), 1)
    expect = (width // 8) * height
    if not str(text).strip():
        return page.tobytes().ljust(expect, b"\xff")[:expect]
    bits = code128_modules(str(text).strip())
    text_band = 30 if width >= 90 else max(18, width // 3)
    bar_height = max(20, width - text_band - 8)
    quiet_modules = 8
    usable = max(1, height - 6)
    module = max(1, usable // (len(bits) + quiet_modules * 2))
    while module > 1 and module * (len(bits) + quiet_modules * 2) > height - 4:
        module -= 1
    barcode_span = module * (len(bits) + quiet_modules * 2)
    y = max(0, (height - barcode_span) // 2) + module * quiet_modules
    x = max(1, (width - text_band - bar_height) // 2)
    draw = ImageDraw.Draw(page)
    for bit in bits:
        if bit == "1":
            draw.rectangle((x, y, x + bar_height - 1, y + module - 1), fill=0)
        y += module
    text_img = Image.new("1", (height - 4, text_band), 1)
    text_draw = ImageDraw.Draw(text_img)
    font = _fit_font(text_draw, shown, text_img.width - 4, text_band - 2)
    text_width, text_height = _text_size(text_draw, shown, font)
    text_draw.text(
        ((text_img.width - text_width) // 2, max(0, (text_img.height - text_height) // 2)),
        shown,
        fill=0,
        font=font,
    )
    turned = text_img.rotate(270, expand=True, fillcolor=1).convert("1", dither=Image.Dither.NONE)
    page.paste(turned, (width - turned.width, max(0, (height - turned.height) // 2)))
    expect = (width // 8) * height
    data = page.convert("1", dither=Image.Dither.NONE).tobytes()
    if len(data) < expect:
        data = data.ljust(expect, b"\xff")
    return data[:expect]


def render_imei_bitmap(imeis: list[str], width: int, height: int) -> bytes:
    imei = re.sub(r"\D", "", imeis[0] if imeis else "")[:15]
    if len(imei) == 15:
        caption = f"{imei[:6]} {imei[6:12]} {imei[12:]}"
    else:
        caption = imei
    return render_barcode_bitmap(imei, width, height, caption)


def label_job(bitmap: bytes, width: int, height: int, width_mm: int, length_mm: int, gap_mm: int) -> bytes:
    return (
        f"\r\nSIZE {width_mm}.0 mm,{length_mm}.0 mm\r\n"
        f"GAP {gap_mm}.0 mm,0 mm\r\n"
        "DIRECTION 1,1\r\n"
        "DENSITY 15\r\n"
        "CLS\r\n"
        f"BITMAP 0,0,{width // 8},{height},1,"
    ).encode() + bitmap + b"\r\nPRINT 1\r\n"


def _write_chunks(port, payload: bytes) -> None:
    for offset in range(0, len(payload), 512):
        port.write(payload[offset : offset + 512])
        port.flush()
        time.sleep(0.02)


def print_imei_label(port_name: str, imeis: list[str]) -> str:
    import serial

    lines = [line for line in imeis if line]
    if not lines:
        raise RuntimeError("Basılacak IMEI yok")
    try:
        port = serial.Serial(port_name, 115200, timeout=2, write_timeout=8)
    except serial.SerialException as exc:
        raise RuntimeError(f"Yazıcı portu açılmadı ({port_name}): {exc}") from exc
    try:
        time.sleep(0.4)
        port.reset_input_buffer()
        port.write(b"\x1b!o\r\n")
        port.flush()
        roll = parse_label_roll(port.read(16)) or DEFAULT_LABEL
        width_mm, length_mm, gap_mm = roll
        width, height = label_dots(width_mm, length_mm)
        bitmap = render_imei_bitmap(lines, width, height)
        _write_chunks(port, label_job(bitmap, width, height, width_mm, length_mm, gap_mm))
    finally:
        port.close()
    return f"{width_mm}x{length_mm} mm etikete {len(lines)} IMEI basıldı ({port_name})"


def barcode_too_long(text: str, height: int) -> bool:
    return len(code128_modules(text)) + 8 > max(1, height - 4)


def wait_for_label(port, length_mm: int, gap_mm: int) -> None:
    """Sonraki işi, şerit fiziksel olarak çıkmadan gönderme. Erken CLS baskıyı yarıda keser."""
    seconds = max(2.8, (length_mm + gap_mm) / 18.0)
    time.sleep(seconds)
    try:
        port.reset_input_buffer()
        port.write(b"\x1b!?\r\n")
        port.flush()
        reply = port.read(1)
    except Exception:
        return
    if reply and reply[0] in (0x02, 0x10, 0x20):
        time.sleep(1.4)


def print_text_labels(port_name: str, texts: list[str], progress=None, stop=None) -> str:
    import serial

    cleaned = [str(item).strip() for item in texts if str(item).strip()]
    if not cleaned:
        raise RuntimeError("Basılacak satır yok")
    try:
        port = serial.Serial(port_name, 115200, timeout=2, write_timeout=8)
    except serial.SerialException as exc:
        raise RuntimeError(f"Yazıcı portu açılmadı ({port_name}): {exc}") from exc
    try:
        time.sleep(0.4)
        port.reset_input_buffer()
        port.write(b"\x1b!o\r\n")
        port.flush()
        width_mm, length_mm, gap_mm = parse_label_roll(port.read(16)) or DEFAULT_LABEL
        width, height = label_dots(width_mm, length_mm)
        done = 0
        skipped = 0
        for index, text in enumerate(cleaned, start=1):
            if stop is not None and stop.is_set():
                break
            if barcode_too_long(text, height):
                skipped += 1
                if progress:
                    progress(index, len(cleaned), f"çok uzun, atlandı: {text}")
                continue
            if progress:
                progress(index, len(cleaned), text)
            bitmap = render_barcode_bitmap(text, width, height)
            _write_chunks(port, label_job(bitmap, width, height, width_mm, length_mm, gap_mm))
            done += 1
            if index < len(cleaned) and not (stop is not None and stop.is_set()):
                if progress:
                    progress(index, len(cleaned), f"{text}  — sonraki etiket bekleniyor")
                wait_for_label(port, length_mm, gap_mm)
    finally:
        port.close()
    note = f"{done} etiket basıldı"
    if skipped:
        note += f", {skipped} satır etikete sığmadı"
    return note
