"""Validated image uploads and conversation-bound image references for inference."""
from io import BytesIO
from pathlib import Path
import base64
import sqlite3
import warnings

IMAGE_EXTENSIONS = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.gif': 'GIF', '.bmp': 'BMP'}
IMAGE_MEDIA = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp', 'GIF': 'image/gif', 'BMP': 'image/bmp'}


def image_info(name, data):
    from PIL import Image, UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != IMAGE_EXTENSIONS.get(Path(name).suffix.lower()):
                    raise ValueError('The image format does not match its filename. Use PNG, JPEG, WebP, GIF or BMP.')
                width, height = image.size
                if width * height > 20_000_000 or max(width, height) > 16384:
                    raise ValueError('This image is too large to decode. Resize it to at most 20 megapixels and 16,384 pixels per side.')
                media = IMAGE_MEDIA[image.format]
                image.verify()
            # Decode too: a valid header alone is insufficient.
            with Image.open(BytesIO(data)) as image:
                image.load()
        return f'Image attachment: {width} × {height} pixels. Vision input; animated images use the first frame.', media, False
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Could not read this image. Paste or choose a valid PNG, JPEG, WebP, GIF or BMP image.') from None


def resolve_image(root, reference, *, turn, conversation):
    """Only expand files bound to this exact user turn; never accept a file path."""
    from hanni.dashboard.attachments import file_id
    if (set(reference) != {'type', 'id', 'turn', 'conversation'} or reference['type'] != 'hanni_image'
            or reference['turn'] != turn or reference['conversation'] != conversation):
        raise ValueError('Image reference does not belong to this message.')
    path = Path(root).resolve() / 'dashboard-chat.sqlite3'
    if path.is_symlink() or not path.is_file():
        raise ValueError('The image attachment store is unavailable.')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT name,data,media_type FROM chat_files WHERE id=? AND turn=? AND conversation=?',
                         (file_id(reference['id']), turn, conversation)).fetchone()
    if not row or not row[2].startswith('image/'):
        raise ValueError('Image is unavailable or belongs to another message.')
    from PIL import Image, ImageOps
    image_info(row[0], row[1])
    with Image.open(BytesIO(row[1])) as image:
        image.seek(0)
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((1536, 1536))
        output = BytesIO()
        image.save(output, format='JPEG', quality=90)
    encoded = base64.b64encode(output.getvalue()).decode('ascii')
    return {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + encoded}}
