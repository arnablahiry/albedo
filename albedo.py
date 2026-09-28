#!/usr/bin/env python3
"""
Albedo: flip light <-> dark while keeping hues
(like CSS `filter: invert(1) hue-rotate(180deg)`).

Modes
  css    exact match of the browser filter invert(1) hue-rotate(180deg)   [default]
  oklab  perceptual: flips lightness in OKLab, keeps hue and chroma

Python
  import albedo
  dark = albedo.flip_figure(fig)          # vector copy of a matplotlib figure, recoloured
  albedo.compare(fig)                     # show original and flipped side by side
  albedo.savefig_pair(fig, "plot.pdf")    # plot.pdf + plot_inverted.pdf
  arr = albedo.flip_image(arr_or_pil)     # any image array / PIL image

Command line
  albedo plot.png                          -> plot_inverted.png
  albedo figure.pdf --dpi 300              -> figure_inverted.pdf
  albedo *.png --mode oklab --black '#0c0d12' -o dark/

Requires numpy and pillow (+ pymupdf for PDF files, matplotlib for figures).
"""
from __future__ import annotations

import argparse
import io
import pickle
import sys
from pathlib import Path

import numpy as np
from PIL import Image

__all__ = ["flip_rgb", "flip_color", "flip_image", "flip_file",
           "flip_figure", "compare", "savefig_pair"]
__version__ = "0.2.0"


# =================================================================== maths
def _hue_matrix(deg: float) -> np.ndarray:
    """The matrix browsers use for CSS hue-rotate() (Filter Effects spec)."""
    t = np.deg2rad(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([
        [0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928],
        [0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283],
        [0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072],
    ])


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
_M1i, _M2i = np.linalg.inv(_M1), np.linalg.inv(_M2)


def _as_rgb01(c) -> np.ndarray:
    """A colour given as '#rrggbb', a name, or an RGB tuple (0-1 or 0-255)."""
    if isinstance(c, str):
        try:
            from matplotlib.colors import to_rgb
            return np.array(to_rgb(c))
        except ImportError:
            c = c.lstrip("#")
            return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    c = np.asarray(c, dtype=float)[:3]
    return c / 255.0 if c.max() > 1 else c


def flip_rgb(rgb, mode: str = "css", hue: float = 0.0, black="#000000", white="#ffffff") -> np.ndarray:
    """Flip lightness of float RGB values in [0, 1], shape (..., 3).

    hue    extra hue rotation in degrees after the flip (0 keeps hues)
    black  darkest output colour (e.g. your dark slide background)
    white  lightest output colour
    """
    rgb = np.asarray(rgb, dtype=float)
    if mode == "css":
        out = np.clip((1.0 - rgb) @ _hue_matrix(180.0 + hue).T, 0.0, 1.0)
    elif mode == "oklab":
        lab = np.cbrt(_srgb_to_linear(rgb) @ _M1.T) @ _M2.T
        lab[..., 0] = 1.0 - lab[..., 0]
        if hue:
            t = np.deg2rad(hue)
            a, b = lab[..., 1].copy(), lab[..., 2].copy()
            lab[..., 1] = a * np.cos(t) - b * np.sin(t)
            lab[..., 2] = a * np.sin(t) + b * np.cos(t)
        out = _linear_to_srgb(((lab @ _M2i.T) ** 3) @ _M1i.T)
    else:
        raise ValueError(f"mode must be 'css' or 'oklab', not {mode!r}")
    lo, hi = _as_rgb01(black), _as_rgb01(white)
    return lo + out * (hi - lo)


def flip_color(color, **opts):
    """Flip one matplotlib colour spec; returns an RGBA tuple (alpha kept)."""
    from matplotlib.colors import to_rgba
    r, g, b, a = to_rgba(color)
    return (*flip_rgb([r, g, b], **opts).tolist(), a)


def _flip_rgba_array(arr, **opts) -> np.ndarray:
    arr = np.array(arr, dtype=float)
    if arr.size:
        arr[..., :3] = flip_rgb(arr[..., :3], **opts)
    return arr


# ================================================================== images
def flip_image(img, **opts):
    """Flip a PIL image or an array (uint8 0-255 or float 0-1, RGB/RGBA/grey).
    Returns the same kind of object it was given. Alpha is kept."""
    if isinstance(img, Image.Image):
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        img = img.convert("RGBA" if has_alpha else "RGB")
        out = flip_image(np.asarray(img), **opts)
        return Image.fromarray(out, img.mode)
    arr = np.asarray(img)
    is_int = np.issubdtype(arr.dtype, np.integer)
    f = arr.astype(float) / 255.0 if is_int else arr.astype(float)
    if f.ndim == 2:
        f = np.repeat(f[..., None], 3, axis=-1)
    f = f.copy()
    f[..., :3] = flip_rgb(f[..., :3], **opts)
    return np.round(np.clip(f, 0, 1) * 255).astype(np.uint8) if is_int else f


def flip_file(src, dst=None, dpi: int = 300, **opts) -> Path:
    """Flip an image or PDF file on disk. Returns the output path."""
    src = Path(src)
    dst = Path(dst) if dst else src.with_name(f"{src.stem}_inverted{src.suffix}")
    if src.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError:
            sys.exit("PDF input needs pymupdf:  pip install pymupdf")
        doc_in, doc_out = pymupdf.open(src), pymupdf.open()
        for page in doc_in:
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = flip_image(Image.frombytes("RGB", (pix.width, pix.height), pix.samples), **opts)
            out_page = doc_out.new_page(width=page.rect.width, height=page.rect.height)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            out_page.insert_image(out_page.rect, stream=buf.getvalue())
        doc_out.save(dst, deflate=True)
    else:
        with Image.open(src) as im:
            info_dpi = im.info.get("dpi")
            out = flip_image(im, **opts)
        if dst.suffix.lower() in (".jpg", ".jpeg"):
            out = out.convert("RGB")
        out.save(dst, **({"dpi": info_dpi} if info_dpi else {}))
    return dst


# ============================================================== matplotlib
def flip_figure(fig, inplace: bool = False, **opts):
    """Recolour a matplotlib figure: lines, text, patches, collections,
    colormaps (and their colorbars) and RGB images. The result stays vector.

    Returns a flipped copy (or `fig` itself with inplace=True).
    opts: mode, hue, black, white (see flip_rgb).
    """
    import matplotlib.cm as mcm
    from matplotlib.collections import Collection
    from matplotlib.colors import Colormap, ListedColormap
    from matplotlib.image import AxesImage, FigureImage
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.text import Text

    if not inplace:
        fig = pickle.loads(pickle.dumps(fig))

    fc = lambda c: flip_color(c, **opts)
    cmaps: dict[int, Colormap] = {}

    def flip_cmap(cm: Colormap) -> Colormap:
        if id(cm) not in cmaps:
            lut = _flip_rgba_array(cm(np.linspace(0, 1, cm.N)), **opts)
            new = ListedColormap(lut, name=f"{cm.name}_albedo")
            for getter, setter in (("get_bad", "set_bad"), ("get_over", "set_over"), ("get_under", "set_under")):
                if hasattr(cm, getter):
                    getattr(new, setter)(fc(getattr(cm, getter)()))
            cmaps[id(cm)] = new
        return cmaps[id(cm)]

    def mapped(a) -> bool:
        return isinstance(a, mcm.ScalarMappable) and a.get_array() is not None

    seen: set[int] = set()
    for a in fig.findobj():
        if id(a) in seen:
            continue
        seen.add(id(a))
        try:
            if isinstance(a, Line2D):
                # marker colours left at "auto" follow the line colour: leave them alone
                marker = {}
                for raw, g, st in (("_markerfacecolor", "get_markerfacecolor", "set_markerfacecolor"),
                                   ("_markerfacecoloralt", "get_markerfacecoloralt", "set_markerfacecoloralt"),
                                   ("_markeredgecolor", "get_markeredgecolor", "set_markeredgecolor")):
                    r = getattr(a, raw, None)
                    if isinstance(r, str) and r.lower() in ("auto", "none"):
                        continue
                    marker[st] = getattr(a, g)()
                a.set_color(fc(a.get_color()))
                for st, c in marker.items():
                    if not (isinstance(c, str) and c.lower() == "none"):
                        getattr(a, st)(fc(c))
            elif isinstance(a, Text):
                a.set_color(fc(a.get_color()))
                bp = a.get_bbox_patch()
                if bp is not None and id(bp) not in seen:
                    seen.add(id(bp))
                    if bp.get_facecolor()[3] > 0:
                        bp.set_facecolor(fc(bp.get_facecolor()))
                    if bp.get_edgecolor()[3] > 0:
                        bp.set_edgecolor(fc(bp.get_edgecolor()))
            elif isinstance(a, (AxesImage, FigureImage)):
                data = a.get_array()
                if data is not None and np.ndim(data) == 3:          # RGB(A) picture
                    a.set_data(flip_image(np.asarray(data)))
                else:
                    a.set_cmap(flip_cmap(a.get_cmap()))
            elif isinstance(a, Collection):
                if mapped(a):
                    a.set_cmap(flip_cmap(a.get_cmap()))
                else:
                    face = a.get_facecolor()
                    if len(face) and np.any(np.asarray(face)[..., 3] > 0):
                        a.set_facecolor(_flip_rgba_array(face, **opts))
                ec = a.get_edgecolor()
                edge_follows_face = str(getattr(a, "_original_edgecolor", "")) == "face"
                if not isinstance(ec, str) and len(ec) and not edge_follows_face \
                        and np.any(np.asarray(ec)[..., 3] > 0) \
                        and not (mapped(a) and getattr(a, "_edge_is_mapped", False)):
                    a.set_edgecolor(_flip_rgba_array(ec, **opts))
            elif isinstance(a, Patch):
                # fully transparent colours stay untouched: re-setting them would let
                # the patch's own alpha make an invisible edge visible
                face, edge = a.get_facecolor(), a.get_edgecolor()
                if face[3] > 0:
                    a.set_facecolor(fc(face))
                if edge[3] > 0:
                    a.set_edgecolor(fc(edge))
        except Exception as e:  # never let one odd artist stop the rest
            print(f"albedo: skipped {type(a).__name__}: {e}", file=sys.stderr)

    # (fig.patch, the figure background, was recoloured with the other patches)
    # style sheets such as dark_background pin rcParams["savefig.facecolor"];
    # make this figure's own savefig default to its (flipped) facecolor instead
    fig.savefig = _SaveWithOwnFace(fig)
    return fig


class _SaveWithOwnFace:
    """savefig that defaults facecolor/edgecolor to the figure's own (picklable)."""
    def __init__(self, fig):
        self.fig = fig

    def __call__(self, *args, **kwargs):
        from matplotlib.figure import Figure
        kwargs.setdefault("facecolor", self.fig.get_facecolor())
        kwargs.setdefault("edgecolor", self.fig.get_edgecolor())
        return Figure.savefig(self.fig, *args, **kwargs)


def savefig_pair(fig, path, suffix: str = "_inverted", flip_opts: dict | None = None, **savefig_kw):
    """Save `fig` to `path` and its flipped copy next to it.
    Returns (original_path, flipped_path)."""
    import matplotlib.pyplot as plt
    path = Path(path)
    fig.savefig(path, **savefig_kw)
    flipped = flip_figure(fig, **(flip_opts or {}))
    out = path.with_name(f"{path.stem}{suffix}{path.suffix}")
    flipped.savefig(out, **savefig_kw)
    plt.close(flipped)
    return path, out


def compare(fig, dpi: int = 120, show: bool = True, **opts):
    """Show the original and flipped figure side by side in one window / cell.
    Returns the comparison figure."""
    import matplotlib.pyplot as plt

    def raster(f):
        buf = io.BytesIO()
        f.savefig(buf, format="png", dpi=dpi, facecolor=f.get_facecolor())
        buf.seek(0)
        return np.asarray(Image.open(buf))

    flipped = flip_figure(fig, **opts)
    a, b = raster(fig), raster(flipped)
    plt.close(flipped)
    h, w = a.shape[:2]
    cmp_fig, axs = plt.subplots(1, 2, figsize=(2 * w / dpi, h / dpi), dpi=dpi)
    for ax, im, title in zip(axs, (a, b), ("original", "albedo")):
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(title, fontsize=9, color="0.5")
    cmp_fig.patch.set_facecolor((0.5, 0.5, 0.5, 0.15))
    cmp_fig.tight_layout(pad=1.0)
    if show:
        plt.show()
    return cmp_fig


# ===================================================================== CLI
def main(argv=None):
    p = argparse.ArgumentParser(prog="albedo", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", type=Path, help="image or PDF files")
    p.add_argument("--mode", choices=["css", "oklab"], default="css")
    p.add_argument("--hue", type=float, default=0.0, help="extra hue shift in degrees (default 0)")
    p.add_argument("--black", default="#000000", help="darkest output colour (default #000000)")
    p.add_argument("--white", default="#ffffff", help="lightest output colour (default #ffffff)")
    p.add_argument("--dpi", type=int, default=300, help="PDF rasterisation resolution (default 300)")
    p.add_argument("-o", "--outdir", type=Path, help="output folder (default: next to input)")
    p.add_argument("--suffix", default="_inverted", help="added to output filename")
    args = p.parse_args(argv)
    opts = dict(mode=args.mode, hue=args.hue, black=args.black, white=args.white)

    for src in args.inputs:
        outdir = args.outdir or src.parent
        outdir.mkdir(parents=True, exist_ok=True)
        dst = flip_file(src, outdir / f"{src.stem}{args.suffix}{src.suffix}", dpi=args.dpi, **opts)
        print(f"{src} -> {dst}")


if __name__ == "__main__":
    main()
