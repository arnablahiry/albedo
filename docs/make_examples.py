"""Make the example figures: a light, paper-style 2x2 figure (a toy matter power
spectrum for three values of Omega_m, plus a lognormal density map drawn from
each spectrum with the same random phases) and its Albedo-flipped dark version,
exactly as the web app shows them.

    python docs/make_examples.py

Writes
  docs/example.png               light original | its flip, as the web app shows them (README)
  docs/example_light.webp        the light figure on its own (web app example,
                                 also embedded into index.html)
"""
import base64
import io
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import albedo  # noqa: E402

STYLE = {
    "font.family": "serif",
    "font.serif": ["STIX Two Text", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 10.5,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "axes.linewidth": 0.8,
    "xtick.direction": "in", "ytick.direction": "in",
    "xtick.top": True, "ytick.right": True,
    "xtick.minor.visible": True, "ytick.minor.visible": True,
    "xtick.major.size": 4, "ytick.major.size": 4,
    "xtick.minor.size": 2, "ytick.minor.size": 2,
    "legend.frameon": False,
}

OMEGAS = [0.25, 0.30, 0.35]
COLOURS = ["#2166ac", "#b35806", "#b2182b"]
L, N = 500.0, 256                    # box size [Mpc/h], grid cells per side
R = 4.0                              # Gaussian smoothing scale [Mpc/h]


def toy_pk(k, om):
    keq = 0.073 * 0.3 * (om / 0.3) ** 2.5        # turnover scale, moves strongly with Omega_m
    amp = 1e4 * (om / 0.3) ** 3                  # and so does the amplitude
    return amp * 2.2 * (k / keq) / (1 + (k / keq) ** 2.6) * (1 + 0.05 * np.sin(k / 0.06))


def density_maps():
    """One lognormal field per Omega_m (same phases), shown as log10(2 + delta)
    as in demo.ipynb: dense knots stand out, voids flatten, so the maps are
    visibly non-Gaussian."""
    kf = 2 * np.pi * np.fft.fftfreq(N, d=L / N)
    kk = np.hypot(kf[:, None], kf[None, :])
    kk[0, 0] = 1
    noise = np.fft.fft2(np.random.default_rng(3).normal(size=(N, N)))
    gs = []
    for om in OMEGAS:
        amp = np.sqrt(toy_pk(kk, om)) * np.exp(-0.5 * (kk * R) ** 2)
        amp[0, 0] = 0
        gs.append(np.real(np.fft.ifft2(noise * amp)))
    s = gs[1].std()                  # common normalisation keeps the Omega_m differences
    maps = []
    for g in gs:
        g = 1.5 * g / s
        delta = np.exp(g - g.var() / 2) - 1
        maps.append(np.log10(2 + delta))
    return maps, 2 * np.pi / L, 1 / R


def make_figure():
    maps, k_fund, k_nyq = density_maps()
    k = np.logspace(-2.5, 0.5, 400)
    fig, axs = plt.subplots(2, 2, figsize=(9.0, 8.2), layout="constrained")
    fig.get_layout_engine().set(rect=(0.035, 0.03, 0.93, 0.94), h_pad=0.06, hspace=0.06)
    ax = axs[0, 0]
    ax.axvspan(k_fund, k_nyq, color="0.5", alpha=0.12, lw=0)
    ax.text(np.sqrt(k_fund * k_nyq), 0.55, "scales in the maps", ha="center", fontsize=9, color="0.35",
            style="italic")
    for om, c in zip(OMEGAS, COLOURS):
        ax.loglog(k, toy_pk(k, om), lw=1.8, color=c, label=rf"$\Omega_m = {om:.2f}$")
    ax.set(xlabel=r"$k\ [h\,\mathrm{Mpc}^{-1}]$", ylabel=r"$P(k)\ [h^{-3}\,\mathrm{Mpc}^{3}]$",
           ylim=(0.3, 1e5), xlim=(k[0], k[-1]))
    ax.set_title("Toy matter power spectrum", loc="left")
    ax.legend(loc="upper right", handlelength=1.6)
    ax.set_box_aspect(1)

    lo, hi = np.percentile(np.concatenate([m.ravel() for m in maps]), [0.2, 99.7])
    ext = [0, L, 0, L]
    for ax, m, om, c in zip([axs[0, 1], axs[1, 0], axs[1, 1]], maps, OMEGAS, COLOURS):
        im = ax.imshow(m, cmap="viridis", vmin=lo, vmax=hi, origin="lower", extent=ext,
                       interpolation="bicubic")
        ax.contour(m, levels=[hi - 0.12 * (hi - lo)], colors="white", linewidths=0.5, origin="lower",
                   extent=ext)
        ax.set_title(rf"Density slice, $\Omega_m = {om:.2f}$", loc="left", color=c)
        ax.set(xlabel=r"$x\ [h^{-1}\,\mathrm{Mpc}]$", ylabel=r"$y\ [h^{-1}\,\mathrm{Mpc}]$")
        ax.tick_params(which="both", color="white")
    cb = fig.colorbar(im, ax=[axs[0, 1], axs[1, 1]], shrink=0.9, pad=0.02, aspect=40)
    cb.set_label(r"$\log_{10}\,(2 + \delta)$", fontsize=13)
    cb.ax.tick_params(which="both", direction="out")
    for ax, tag in zip(axs.flat, "abcd"):
        ax.text(0.03, 0.97, f"({tag})", transform=ax.transAxes, ha="left", va="top", fontsize=10.5,
                fontweight="bold", color="black" if tag == "a" else "white")
    return fig


def png(fig, dpi):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    buf.seek(0)
    return Image.open(buf).convert("RGB")


with plt.rc_context(STYLE):
    light = make_figure()
    web = png(light, 170)

web.save(HERE / "example_light.webp", quality=88, method=6)
uri = "data:image/webp;base64," + base64.b64encode((HERE / "example_light.webp").read_bytes()).decode()
page = HERE.parent / "index.html"            # the web app embeds the example, so it works from file://
html, n = re.subn(r'const EXAMPLE = "[^"]*";', f'const EXAMPLE = "{uri}";', page.read_text())
if n != 1:
    raise SystemExit("index.html: expected one `const EXAMPLE = ...` line")
page.write_text(html)

# README pair: exactly what the web app shows, i.e. the embedded image and its
# pixel flip in the default CSS mode
with Image.open(HERE / "example_light.webp") as im:
    a = im.convert("RGB")
b = albedo.flip_image(a)
gap = 24
pair = Image.new("RGBA", (a.width + b.width + gap, a.height), (0, 0, 0, 0))
pair.paste(a, (0, 0))
pair.paste(b, (a.width + gap, 0))
pair.save(HERE / "example.png", optimize=True)
print(f"example.png {pair.size}, example_light.webp {web.size}, embedded in index.html ({len(uri) / 1e3:.0f} kB)")
