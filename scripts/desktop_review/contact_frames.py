"""Arrange existing genuine native captures for independent layout inspection.

These sheets are viewing aids; individual framed screenshots remain evidence.
No application interface, mockup, synthetic scene or pixel edit is generated.
"""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageOps

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path)
args=parser.parse_args()
sizes=[(1920,1080),(1440,900),(1366,768),(900,650)]
routes=sorted({path.name.rsplit('-',2)[0] for path in args.directory.glob('*-native.png')})
for route in routes:
    canvas=Image.new('RGB',(2400,1500),'#424242')
    draw=ImageDraw.Draw(canvas)
    for index,(width,height) in enumerate(sizes):
        source=args.directory/f'{route}-{width}x{height}-native.png'
        if not source.exists():
            continue
        with Image.open(source) as original:
            preview=ImageOps.contain(original,(1200,720))
            x,y=(index%2)*1200,(index//2)*750
            draw.text((x+10,y+6),f'{route}: actual {width}x{height} native frame', fill='white')
            canvas.paste(preview,(x,y+25))
    canvas.save(args.directory/f'{route}-contact.png')
