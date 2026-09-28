"""Tests for albedo. Run with:  pytest"""
import io
import pickle

import numpy as np
import pytest
from PIL import Image

import albedo

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgba  # noqa: E402

RNG = np.random.default_rng(0)
MODES = ["css", "oklab"]


# ------------------------------------------------------------------ colour maths
@pytest.mark.parametrize("mode", MODES)
def test_black_and_white_swap(mode):
    out = albedo.flip_rgb([[0, 0, 0], [1, 1, 1]], mode=mode)
    np.testing.assert_allclose(out, [[1, 1, 1], [0, 0, 0]], atol=1e-6)


@pytest.mark.parametrize("mode", MODES)
def test_greys_stay_grey_and_round_trip(mode):
    g = np.linspace(0, 1, 21)[:, None].repeat(3, 1)
    once = albedo.flip_rgb(g, mode=mode)
    np.testing.assert_allclose(once, once[:, :1].repeat(3, 1), atol=1e-6)      # still neutral
    assert np.all(np.diff(once[:, 0]) <= 1e-9)                                 # order reversed
    np.testing.assert_allclose(albedo.flip_rgb(once, mode=mode), g, atol=1e-6)


def test_css_mode_matches_browser_filter():
    # invert(1) then the Filter Effects hue-rotate(180deg) matrix, clipped
    M = np.array([[-0.574, 1.430, 0.144], [0.426, 0.430, 0.144], [0.426, 1.430, -0.856]])
    c = RNG.uniform(size=(500, 3))
    np.testing.assert_allclose(albedo.flip_rgb(c), np.clip((1 - c) @ M.T, 0, 1), atol=1e-9)


def test_css_matrix_is_an_involution_before_clipping():
    H = albedo._hue_matrix(180)
    np.testing.assert_allclose(H @ H, np.eye(3), atol=1e-12)


def test_hue_is_kept():
    import colorsys
    for rgb in [(0.12, 0.47, 0.71), (0.17, 0.63, 0.17), (0.58, 0.40, 0.74)]:   # tab blue/green/purple
        h0 = colorsys.rgb_to_hsv(*rgb)[0]
        h1 = colorsys.rgb_to_hsv(*albedo.flip_rgb(rgb))[0]
        assert min(abs(h0 - h1), 1 - abs(h0 - h1)) < 0.03


def test_hue_zero_is_default_and_hue_shift_changes_colour():
    c = [0.2, 0.5, 0.8]
    np.testing.assert_allclose(albedo.flip_rgb(c), albedo.flip_rgb(c, hue=0))
    assert not np.allclose(albedo.flip_rgb(c), albedo.flip_rgb(c, hue=90))


@pytest.mark.parametrize("black", ["#0c0d12", (12, 13, 18), (12 / 255, 13 / 255, 18 / 255)])
def test_output_range(black):
    out = albedo.flip_rgb([[1, 1, 1], [0, 0, 0]], black=black, white="#e8e6df")
    np.testing.assert_allclose(out[0] * 255, [12, 13, 18], atol=1e-6)
    np.testing.assert_allclose(out[1] * 255, [0xe8, 0xe6, 0xdf], atol=1e-6)


def test_bad_arguments():
    with pytest.raises(ValueError):
        albedo.flip_rgb([0.5, 0.5, 0.5], mode="nope")
    with pytest.raises(ValueError):
        albedo.flip_rgb([0.5, 0.5], mode="css")
    with pytest.raises(ValueError):
        albedo.flip_rgb([0.5, 0.5, 0.5], black="notacolour")


def test_out_of_range_input_is_clipped():
    np.testing.assert_allclose(albedo.flip_rgb([2, -1, 0.5]), albedo.flip_rgb([1, 0, 0.5]))


def test_flip_color_keeps_alpha():
    r, g, b, a = albedo.flip_color((0.2, 0.6, 0.3, 0.4))
    assert a == 0.4
    assert albedo.flip_color("white")[:3] == pytest.approx((0, 0, 0))


# ----------------------------------------------------------------------- images
@pytest.mark.parametrize("dtype,top", [(np.uint8, 255), (np.uint16, 65535)])
def test_flip_image_integer_dtypes(dtype, top):
    img = np.zeros((4, 5, 3), dtype)
    out = albedo.flip_image(img)
    assert out.dtype == dtype and out.shape == img.shape
    assert np.all(out == top)


def test_flip_image_float_and_grey_and_alpha():
    f = RNG.uniform(size=(6, 7, 3)).astype(np.float32)
    assert albedo.flip_image(f).dtype == np.float32

    grey = np.full((3, 3), 255, np.uint8)
    out = albedo.flip_image(grey)
    assert out.shape == (3, 3, 3) and np.all(out == 0)

    rgba = np.dstack([np.zeros((3, 3, 3), np.uint8), np.arange(9, dtype=np.uint8).reshape(3, 3)])
    out = albedo.flip_image(rgba)
    np.testing.assert_array_equal(out[..., 3], rgba[..., 3])


def test_flip_image_rejects_bad_shapes():
    with pytest.raises(ValueError):
        albedo.flip_image(np.zeros((2, 2, 2)))


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P", "LA"])
def test_flip_image_pil_modes(mode):
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 128)).convert(mode)
    out = albedo.flip_image(img)
    assert isinstance(out, Image.Image) and out.size == (8, 8)
    assert out.getpixel((0, 0))[:3] == (255, 255, 255)
    assert ("A" in out.mode) == ("A" in mode)


def test_flip_file_png_and_errors(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (10, 10), (0, 0, 0)).save(src, dpi=(150, 150))
    dst = albedo.flip_file(src)
    assert dst == tmp_path / "a_inverted.png"
    with Image.open(dst) as im:
        assert im.getpixel((0, 0)) == (255, 255, 255)
        assert round(im.info["dpi"][0]) == 150
    with pytest.raises(ValueError):
        albedo.flip_file(src, src)
    with pytest.raises(FileNotFoundError):
        albedo.flip_file(tmp_path / "missing.png")


def test_flip_file_jpeg_with_alpha_source(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(src)
    dst = albedo.flip_file(src, tmp_path / "b.jpg")
    with Image.open(dst) as im:
        assert im.mode == "RGB"


def test_flip_file_pdf(tmp_path):
    pytest.importorskip("pymupdf")
    fig, ax = plt.subplots(figsize=(2, 2))
    fig.patch.set_facecolor("black")
    src = tmp_path / "f.pdf"
    fig.savefig(src)
    plt.close(fig)
    dst = albedo.flip_file(src, dpi=50)
    import pymupdf
    page = pymupdf.open(dst)[0]
    pix = page.get_pixmap(dpi=20)
    assert pix.pixel(1, 1)[:3] == (255, 255, 255)


# ------------------------------------------------------------------- matplotlib
def dark_figure():
    with plt.style.context("dark_background"):
        fig, axs = plt.subplots(1, 3, figsize=(6, 2))
        axs[0].plot([0, 1], [0, 1], "C0", marker="o", mfc="none")
        axs[0].hist(RNG.normal(size=200), alpha=0.6)
        axs[0].text(0.5, 0.5, "box", bbox=dict(fc="C2", alpha=0.5))
        sc = axs[1].scatter(*RNG.normal(size=(2, 50)), c=RNG.uniform(size=50), cmap="viridis")
        fig.colorbar(sc, ax=axs[1])
        axs[2].imshow(RNG.uniform(size=(5, 5, 3)))
    return fig


def render(fig, dpi=40):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    buf.seek(0)
    return np.asarray(Image.open(buf).convert("RGB")).astype(int)


def test_flip_figure_leaves_original_alone():
    fig = dark_figure()
    before, line_colour = render(fig), fig.axes[0].lines[0].get_color()
    flipped = albedo.flip_figure(fig)
    assert flipped is not fig
    np.testing.assert_array_equal(render(fig), before)
    assert fig.axes[0].lines[0].get_color() == line_colour
    plt.close("all")


def test_flip_figure_matches_pixel_flip():
    fig = dark_figure()
    vector = render(albedo.flip_figure(fig))
    pixels = albedo.flip_image(render(fig).astype(np.uint8)).astype(int)
    diff = np.abs(vector - pixels).max(-1)
    assert np.median(diff) <= 2
    assert np.mean(diff > 40) < 0.02          # only anti-aliased edges differ
    plt.close("all")


def test_flip_figure_inplace_and_options():
    fig = dark_figure()
    out = albedo.flip_figure(fig, inplace=True, white="#fafafa")
    assert out is fig
    assert to_rgba(fig.patch.get_facecolor())[:3] == pytest.approx((0xfa / 255,) * 3)
    with pytest.raises(ValueError):
        albedo.flip_figure(fig, mode="nope")
    plt.close("all")


def test_colorbar_follows_flipped_colormap():
    fig = dark_figure()
    flipped = albedo.flip_figure(fig)
    sc = flipped.axes[1].collections[0]
    cbar_mesh = [c for c in flipped.axes[-1].collections if c.get_array() is not None][0]
    assert sc.get_cmap().name.endswith("_albedo")
    assert cbar_mesh.get_cmap().name.endswith("_albedo")
    plt.close("all")


def test_flipped_figure_saves_its_own_background(tmp_path):
    fig = dark_figure()
    with plt.style.context("dark_background"):              # pins savefig.facecolor = black
        flipped = albedo.flip_figure(fig)
        flipped.savefig(tmp_path / "x.png", dpi=20)
    with Image.open(tmp_path / "x.png") as im:
        assert im.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
    pickle.dumps(flipped)                                    # still picklable
    plt.close("all")


def test_savefig_pair_and_vector_output(tmp_path):
    fig = dark_figure()
    a, b = albedo.savefig_pair(fig, tmp_path / "p.pdf", flip_opts={"mode": "oklab"})
    assert a.exists() and b.exists() and b.name == "p_inverted.pdf"
    assert b"/Font" in b.read_bytes() or b"BT" in b.read_bytes()
    plt.close("all")


def test_compare_returns_figure():
    fig = dark_figure()
    cmp = albedo.compare(fig, show=False, dpi=30)
    assert len(cmp.axes) == 2
    plt.close("all")


# -------------------------------------------------------------------------- CLI
def test_cli(tmp_path, capsys):
    src = tmp_path / "c.png"
    Image.new("RGB", (4, 4), (255, 255, 255)).save(src)
    assert albedo.main([str(src), "--black", "#0c0d12", "-o", str(tmp_path / "out")]) == 0
    with Image.open(tmp_path / "out" / "c_inverted.png") as im:
        assert im.getpixel((0, 0)) == (12, 13, 18)
    assert albedo.main([str(tmp_path / "missing.png")]) == 1
    assert "no such file" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        albedo.main([str(src), "--black", "notacolour"])


def test_colorbar_still_follows_its_image_after_copy():
    fig, ax = plt.subplots()
    im = ax.imshow(RNG.uniform(size=(4, 4)))
    fig.colorbar(im)
    flipped = albedo.flip_figure(fig)
    flipped.axes[0].images[0].set_cmap("magma")
    mesh = [c for c in flipped.axes[1].collections if c.get_array() is not None][0]
    assert mesh.get_cmap().name == "magma"
    plt.close("all")


def test_colorbar_follows_clim_after_copy():
    fig, ax = plt.subplots()
    im = ax.imshow(RNG.uniform(size=(4, 4)))
    fig.colorbar(im)
    flipped = albedo.flip_figure(fig)
    flipped.axes[0].images[0].set_clim(0, 10)
    assert flipped.axes[0].images[0].colorbar.vmax == 10
    plt.close("all")
