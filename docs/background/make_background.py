"""Make the web app's animated background: a wide lognormal density field in
viridis (the same recipe as the density field in demo.ipynb) and its Albedo flip.

The field is built in Fourier space, so it is periodic: the image tiles
seamlessly left to right, which lets the page pan it in an endless loop.

    python docs/background/make_background.py
"""
import sys
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import albedo  # noqa: E402

W, H = 3840, 1920            # 2:1, tiles horizontally
BOX = 2.5                    # field spans this many "readme boxes" vertically
SMOOTH = 1.5                 # Gaussian smoothing in pixels, removes pixel grain
QUALITY = 82

rng = np.random.default_rng(7)
kx = np.fft.fftfreq(W)[None, :] * W / H * BOX
ky = np.fft.fftfreq(H)[:, None] * BOX
kk = np.hypot(kx, ky)
kk[0, 0] = 1
spec = kk ** -1.4 * np.exp(-0.5 * (np.hypot(np.fft.fftfreq(W)[None, :], np.fft.fftfreq(H)[:, None])
                                   * 2 * np.pi * SMOOTH) ** 2)
spec[0, 0] = 0
field = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(size=(H, W))) * spec))
delta = np.exp(field / field.std()) - 1
img = np.log10(2 + delta)
lo, hi = np.percentile(img, [0.5, 99.5])
rgb = colormaps["viridis"](np.clip((img - lo) / (hi - lo), 0, 1))[..., :3]
rgb8 = np.round(rgb * 255).astype(np.uint8)

for name, arr in (("density", rgb8), ("density_albedo", albedo.flip_image(rgb8))):
    out = HERE / f"{name}.webp"
    Image.fromarray(arr).save(out, quality=QUALITY, method=6)
    print(f"{out.name}: {arr.shape[1]}x{arr.shape[0]}, {out.stat().st_size / 1e6:.1f} MB")
