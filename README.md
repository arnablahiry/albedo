# Albedo

Flip plots between dark and light backgrounds while keeping their hues: blue stays blue, orange stays orange. Useful for moving figures between dark slides and light papers.

It does the same thing as the CSS filter `invert(1) hue-rotate(180deg)`.

## Web app

Open `index.html` in a browser. Drop in an image or PDF, adjust the settings, and download the result as PNG, JPEG, WebP or PDF. Everything runs locally in the browser.

Settings:

- **Mode**: `CSS` matches the browser filter exactly; `OKLab` flips perceived lightness and keeps hue and chroma.
- **Hue shift**: extra hue rotation after the flip (0° keeps hues).
- **Output range**: darkest and lightest output colours, e.g. set the darkest to your slide background.
- **PDF render DPI**, **image format**, **quality**, and lossless or JPEG pages for PDF output.

## Command line

```bash
pip install -r requirements.txt

python albedo.py plot.png                     # -> plot_inverted.png
python albedo.py figure.pdf --dpi 300         # -> figure_inverted.pdf
python albedo.py *.png --mode oklab -o dark/  # batch into a folder
```

PDF pages are rasterised at the chosen DPI, so PDF output is not vector.
