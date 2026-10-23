"""Build the repository-native h. Windows icon; no remote assets or fonts."""
from pathlib import Path
from PIL import Image, ImageDraw

SIZE = 256
image = Image.new('RGBA', (SIZE,SIZE), '#18191c')
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((6,6,250,250), radius=48, fill='#202125', outline='#3d424d', width=3)
draw.rounded_rectangle((57,54,87,196), radius=5, fill='#eeeeef')
draw.arc((70,97,168,181), 180, 360, fill='#eeeeef', width=28)
draw.rectangle((140,138,168,196), fill='#eeeeef')
draw.ellipse((183,166,213,196), fill='#a4c2e9')
image.save(Path(__file__).with_name('hanni.ico'), sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
