"""Encode a 120-frame turntable as an eight-second looping GIF (requires Pillow)."""
import argparse
from pathlib import Path
from PIL import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('frames', type=Path)
p.add_argument('output', type=Path)
args = p.parse_args()
paths = sorted(args.frames.glob('[0-9][0-9][0-9][0-9].png'))
if len(paths) != 120:
    raise SystemExit('Expected 120 PNG frames')
with Image.open(paths[0]) as first:
    width, height = first.size
sample = Image.new('RGB', (width, height))
thumb = (width//4, height//2)
for j, i in enumerate(range(0, 120, 15)):
    with Image.open(paths[i]) as im:
        sample.paste(im.convert('RGB').resize(thumb), ((j % 4)*thumb[0], (j // 4)*thumb[1]))
palette = sample.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
frames = []
for path in paths:
    with Image.open(path) as im:
        assert im.size == (width,height), 'Inconsistent frame dimensions'
        frames.append(im.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE))
args.output.parent.mkdir(parents=True, exist_ok=True)
# GIF timing uses 10ms units: 70+70+60ms per three frames gives exactly 8s.
frames[0].save(args.output, save_all=True, append_images=frames[1:],
               duration=[70,70,60]*40, loop=0, optimize=False, disposal=1)
with Image.open(args.output) as gif:
    assert gif.n_frames == 120 and gif.size == (width,height) and gif.info['loop'] == 0
    duration = 0
    for i in range(gif.n_frames):
        gif.seek(i); duration += gif.info['duration']
    assert duration == 8000
print(f'{args.output.name}: 120 frames, 8 seconds, {args.output.stat().st_size:,} bytes')
