"""Make the web app's icons from docs/images/logo.png.

    python docs/images/make_icons.py

Writes, next to this file
  logo-heading.webp      small transparent logo shown left of the page heading
  favicon-32.png         browser tab icon
  favicon-192.png        larger icon (Android, bookmarks)
  apple-touch-icon.png   180 px, opaque (iOS shows transparency as black)
  social.png             512 px, opaque, the image shown in link previews
The opaque icons sit on a split background, light behind the original half
of the face and dark behind its flipped half.
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
LIGHT, DARK = (245, 244, 240, 255), (16, 15, 12, 255)      # the page's --bg in each theme
SPLIT = 358 / 635                                          # where the flipped half starts

logo = Image.open(HERE / "logo.png").convert("RGBA")
logo = logo.crop(logo.getbbox())
split_px = SPLIT * 635 - Image.open(HERE / "logo.png").getbbox()[0]   # split, in cropped pixels


def fit(size, pad):
    """Logo scaled to fit a size x size square with `pad` margin; returns (image, x, y)."""
    s = (size - 2 * pad) / max(logo.size)
    im = logo.resize((round(logo.width * s), round(logo.height * s)), Image.LANCZOS)
    return im, (size - im.width) // 2, (size - im.height) // 2, s


def square(size, pad, opaque):
    im, x, y, s = fit(size, pad)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if opaque:
        cut = x + round(split_px * s)
        d = ImageDraw.Draw(out)
        d.rectangle([0, 0, cut - 1, size], fill=LIGHT)
        d.rectangle([cut, 0, size, size], fill=DARK)
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
