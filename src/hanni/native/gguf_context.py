"""Read the declared context from GGUF metadata without loading tensor data."""
from pathlib import Path
import struct

_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


def context_limit(path):
    try:
        path = Path(path)
        stat = path.stat()
        return _read(str(path), stat.st_size)
    except (OSError, ValueError, struct.error, UnicodeError, OverflowError):
        return None


def _read(path, size):
    with open(path, 'rb') as stream:
        def number(fmt):
            return struct.unpack('<' + fmt, stream.read(struct.calcsize('<' + fmt)))[0]

        def length():
            value = number('Q')
            if value > size or value > 16_000_000:
                raise ValueError('Oversized GGUF metadata.')
            return value

        def skip(kind, depth=0):
            if depth > 3:
                raise ValueError('Nested GGUF metadata.')
            if kind in _SIZES:
                stream.seek(_SIZES[kind], 1)
            elif kind == 8:
                stream.seek(length(), 1)
            elif kind == 9:
                element, count = number('I'), length()
                if element in _SIZES:
                    stream.seek(_SIZES[element] * count, 1)
                else:
                    for _ in range(count):
                        skip(element, depth + 1)
            else:
                raise ValueError('Unknown GGUF metadata type.')
            if stream.tell() > size:
                raise ValueError('Truncated GGUF metadata.')

        if stream.read(4) != b'GGUF' or number('I') not in {2, 3}:
            return None
        number('Q')
        count = length()
        for _ in range(min(count, 1_000_000)):
            key_size = length()
            if key_size > 4096:
                raise ValueError('Oversized GGUF metadata key.')
            key = stream.read(key_size).decode('utf-8')
            kind = number('I')
            if key.endswith('.context_length') and kind in {4, 10}:
                value = number('I' if kind == 4 else 'Q')
                return value if value > 0 else None
            skip(kind)
    return None
