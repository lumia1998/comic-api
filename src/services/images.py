import hashlib
import io
from urllib.parse import urlparse

from PIL import Image


def jm_image_filename(url):
    return urlparse(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def jm_scramble_num(chapter_id, filename):
    try:
        number = int(chapter_id)
    except (ValueError, TypeError):
        return 0
    if number < 220980:
        return 0
    if number < 268850:
        return 10
    digest = hashlib.md5(f"{number}{filename}".encode()).hexdigest()
    return ord(digest[-1]) % (10 if number < 421926 else 8) * 2 + 2


def descramble_jm_image(data, chapter_id, url, count=None):
    count = jm_scramble_num(chapter_id, jm_image_filename(url)) if count is None else count
    if count <= 1:
        return data
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        step, remainder = divmod(height, count)
        if not step:
            return data
        with Image.new(img.mode, (width, height)) as fixed:
            for index in range(count):
                y = height - step * (index + 1) - remainder
                size = step + (remainder if index == 0 else 0)
                fixed.paste(img.crop((0, y, width, y + size)),
                            (0, step * index + (0 if index == 0 else remainder)))
            output = io.BytesIO()
            fixed.save(output, format=img.format or "JPEG")
            return output.getvalue()
