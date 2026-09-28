#!/usr/bin/env python3
"""
Flip light <-> dark while keeping hues (like CSS `filter: invert(1) hue-rotate(180deg)`).

Works on images (png, jpg, tiff, webp, ...) and PDFs (every page is rasterised).

Modes
  css    exact match of the browser filter  invert(1) hue-rotate(180deg)   [default]
  oklab  perceptual: flips lightness in OKLab, keeps hue *and* chroma exactly
         (usually a bit more faithful for colormaps like viridis / RdBu)

Usage
  python albedo.py plot.png                    -> plot_inverted.png
  python albedo.py figure.pdf --dpi 300        -> figure_inverted.pdf
  python albedo.py *.png --mode oklab -o out/  (batch, into a folder)

Requires: numpy, pillow   (+ pymupdf for PDFs:  pip install pymupdf)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- css mode
def _css_hue_rotate_matrix(deg: float) -> np.ndarray:
    """The exact matrix browsers use for hue-rotate() (Filter Effects spec)."""
    t = np.deg2rad(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([
        [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928],
        [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283],
        [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072],
    ])


def invert_css(rgb: np.ndarray, hue_deg: float = 180.0) -> np.ndarray:
    """rgb: float array in [0,1], shape (..., 3)."""
    out = 1.0 - rgb                                   # invert(1)
    out = out @ _css_hue_rotate_matrix(hue_deg).T     # hue-rotate(180deg)
    return np.clip(out, 0.0, 1.0)


# -------------------------------------------------------------- oklab mode
def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def invert_oklab(rgb: np.ndarray) -> np.ndarray:
    lin = _srgb_to_linear(rgb)
    lab = np.cbrt(lin @ _M1.T) @ _M2.T
    lab[..., 0] = 1.0 - lab[..., 0]                   # flip lightness only
    lms = (lab @ np.linalg.inv(_M2).T) ** 3
    return _linear_to_srgb(lms @ np.linalg.inv(_M1).T)


# ------------------------------------------------------------------ driver
def process_pil(img: Image.Image, mode: str) -> Image.Image:
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    arr = np.asarray(img).astype(np.float64) / 255.0
    rgb = arr[..., :3]
    rgb = invert_css(rgb) if mode == "css" else invert_oklab(rgb)
    arr = np.concatenate([rgb, arr[..., 3:]], axis=-1)   # alpha untouched
    return Image.fromarray(np.round(arr * 255).astype(np.uint8), img.mode)


def process_pdf(src: Path, dst: Path, mode: str, dpi: int):
    try:
        import pymupdf as fitz
    except ImportError:
        sys.exit("PDF input needs pymupdf:  pip install pymupdf")
    doc_in, doc_out = fitz.open(src), fitz.open()
    for page in doc_in:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = process_pil(img, mode)
        out_page = doc_out.new_page(width=page.rect.width, height=page.rect.height)
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="PNG")
        out_page.insert_image(out_page.rect, stream=buf.getvalue())
    doc_out.save(dst, deflate=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", type=Path, help="image or PDF files")
    p.add_argument("--mode", choices=["css", "oklab"], default="css")
    p.add_argument("--dpi", type=int, default=300, help="PDF rasterisation resolution (default 300)")
    p.add_argument("-o", "--outdir", type=Path, help="output folder (default: next to input)")
    p.add_argument("--suffix", default="_inverted", help="added to output filename")
    args = p.parse_args()

    for src in args.inputs:
        outdir = args.outdir or src.parent
        outdir.mkdir(parents=True, exist_ok=True)
        dst = outdir / f"{src.stem}{args.suffix}{src.suffix}"
        if src.suffix.lower() == ".pdf":
            process_pdf(src, dst, args.mode, args.dpi)
        else:
            with Image.open(src) as im:
                dpi = im.info.get("dpi")
                out = process_pil(im, args.mode)
                if src.suffix.lower() in (".jpg", ".jpeg"):
                    out = out.convert("RGB")
                out.save(dst, **({"dpi": dpi} if dpi else {}))
        print(f"{src} -> {dst}")


if __name__ == "__main__":
    main()
