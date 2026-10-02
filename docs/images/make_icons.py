"""Make the web app's icons from docs/images/logo.png.

    python docs/images/make_icons.py

Writes, next to this file
  logo-heading.webp      small transparent logo shown left of the page heading
  favicon-32.png         browser tab icon
  favicon-192.png        larger icon (Android, bookmarks)
  apple-touch-icon.png   180 px, opaque (iOS shows transparency as black)
  social.png             512 px, opaque, the image shown in link previews
The opaque icons sit on 50% grey, the one colour Albedo's flip leaves unchanged
(apps such as WhatsApp fill transparency unpredictably, so the preview needs a
solid background).
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
GREY = (128, 128, 128)                                     # invert + hue-rotate(180deg) maps it to itself

logo = Image.open(HERE / "logo.png").convert("RGBA")
logo = logo.crop(logo.getbbox())


def fit(size, pad):
    """Logo scaled to fit a size x size square with `pad` margin; returns (image, x, y)."""
    s = (size - 2 * pad) / max(logo.size)
    im = logo.resize((round(logo.width * s), round(logo.height * s)), Image.LANCZOS)
    return im, (size - im.width) // 2, (size - im.height) // 2


def square(size, pad, opaque):
    im, x, y = fit(size, pad)
    out = Image.new("RGBA", (size, size), (*GREY, 255) if opaque else (0, 0, 0, 0))
    if opaque:
        y = size - im.height                               # the bust is cut flat: sit it on the bottom edge
    out.alpha_composite(im, (x, y))
    return out if not opaque else out.convert("RGB")


h = 240                                                    # 2x the largest heading size
logo.resize((round(logo.width * h / logo.height), h), Image.LANCZOS).save(
    HERE / "logo-heading.webp", quality=90, method=6)
square(32, 1, False).save(HERE / "favicon-32.png", optimize=True)
square(192, 6, False).save(HERE / "favicon-192.png", optimize=True)
square(180, 16, True).save(HERE / "apple-touch-icon.png", optimize=True)
square(512, 44, True).save(HERE / "social.png", optimize=True)
for f in ("logo-heading.webp", "favicon-32.png", "favicon-192.png", "apple-touch-icon.png", "social.png"):
    print(f, Image.open(HERE / f).size, f"{(HERE / f).stat().st_size / 1e3:.0f} kB")
