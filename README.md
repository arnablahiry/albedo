# Albedo

Flip plots between dark and light backgrounds while keeping their hues: blue stays blue, orange stays orange. Useful for moving figures between dark slides and light papers.

The default mode does the same thing as the CSS filter `invert(1) hue-rotate(180deg)`.

## Install

```bash
pip install -e ~/repos/albedo[all]
```

This gives you `import albedo` everywhere and an `albedo` command. `[all]` adds matplotlib and PDF support.

## In Python with matplotlib

```python
import matplotlib.pyplot as plt
import albedo

fig, ax = plt.subplots()
ax.plot(x, y)

dark = albedo.flip_figure(fig)            # flipped copy; fig is untouched
dark.savefig("plot_dark.pdf")             # still vector

albedo.compare(fig)                       # original and flipped side by side
albedo.savefig_pair(fig, "plot.pdf")      # writes plot.pdf and plot_inverted.pdf
```

`flip_figure` recolours the figure itself (lines, markers, text, patches, fills, scatter, colormaps and their colorbars, RGB images), so saved PDFs and SVGs stay vector. Use `inplace=True` to recolour `fig` directly.

Other helpers:

```python
albedo.flip_image(array_or_pil_image)     # returns the same type
albedo.flip_color("tab:blue")             # one colour -> RGBA tuple
albedo.flip_file("figure.pdf", dpi=300)   # a file on disk
```

All of them take the same options:

| Option  | Default     | Meaning |
|---------|-------------|---------|
| `mode`  | `"css"`     | `"css"` matches the browser filter; `"oklab"` flips perceived lightness and keeps hue and chroma |
| `hue`   | `0`         | extra hue rotation in degrees after the flip |
| `black` | `"#000000"` | darkest output colour, e.g. your slide background |
| `white` | `"#ffffff"` | lightest output colour |

## Command line

```bash
albedo plot.png                                  # -> plot_inverted.png
albedo figure.pdf --dpi 300                      # -> figure_inverted.pdf
albedo *.png --mode oklab --black '#0c0d12' -o dark/
```

PDF files are rasterised at `--dpi`, so the output PDF is not vector. For vector output, flip the matplotlib figure instead.

## Web app

Open `index.html` in a browser. Drop in an image or PDF, adjust the settings, and download the result as PNG, JPEG, WebP or PDF. Everything runs locally in the browser.
