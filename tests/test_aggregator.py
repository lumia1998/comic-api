import hashlib
import io
import sys
import types

import pytest
from PIL import Image


clients = types.ModuleType("src.clients")
clients.JmClient = lambda: object()
clients.BikaClient = lambda: object()
sys.modules.setdefault("src.clients", clients)

from src.services.aggregator import AggregatorService


def expected_jm_scramble_num(chapter_id: int, filename: str) -> int:
    if chapter_id < 220980:
        return 0
    if chapter_id < 268850:
        return 10
    modulus = 10 if chapter_id < 421926 else 8
    digest = hashlib.md5(f"{chapter_id}{filename}".encode("utf-8")).hexdigest()
    return ord(digest[-1]) % modulus * 2 + 2


def striped_image(width: int = 6, height: int = 23) -> Image.Image:
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        color = (y * 7 % 256, y * 11 % 256, y * 17 % 256)
        for x in range(width):
            pixels[x, y] = color
    return image


def scramble_image(decoded: Image.Image, num: int) -> Image.Image:
    width, height = decoded.size
    move = height // num
    over = height % num
    scrambled = Image.new("RGB", (width, height))
    for index in range(num):
        src_y = move * index
        dst_y = height - move * (index + 1) - over
        current_height = move
        if index == 0:
            current_height += over
        else:
            src_y += over
        scrambled.paste(decoded.crop((0, src_y, width, src_y + current_height)), (0, dst_y))
    return scrambled


def image_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_jm_scramble_num_matches_jmcomic_thresholds():
    service = AggregatorService.__new__(AggregatorService)

    assert service._jm_image_filename("https://cdn.test/media/photos/268850/00001.jpg?v=1") == "00001"
    assert service._jm_scramble_num("220979", "00001") == 0
    assert service._jm_scramble_num("220980", "00001") == 10
    assert service._jm_scramble_num("268850", "00001") == expected_jm_scramble_num(268850, "00001")
    assert service._jm_scramble_num("421926", "00001") == expected_jm_scramble_num(421926, "00001")


def test_descramble_jm_image_restores_reordered_slices(monkeypatch):
    service = AggregatorService.__new__(AggregatorService)
    decoded = striped_image()
    scrambled = scramble_image(decoded, num=4)
    monkeypatch.setattr(service, "_jm_scramble_num", lambda _chapter_id, _filename: 4)

    restored = Image.open(io.BytesIO(service._descramble_jm_image(
        image_bytes(scrambled),
        "268850",
        "https://cdn.test/media/photos/268850/00001.png",
    )))

    assert list(restored.getdata()) == list(decoded.getdata())


def test_encrypt_pdf_requires_password_when_pypdf_is_installed(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    service = AggregatorService.__new__(AggregatorService)
    pdf_path = tmp_path / "chapter.pdf"
    Image.new("RGB", (16, 16), "white").save(pdf_path, "PDF")

    service._encrypt_pdf(str(pdf_path), "123456")

    reader = pypdf.PdfReader(str(pdf_path))
    assert reader.is_encrypted
    assert reader.decrypt("123456")
    assert len(reader.pages) == 1
