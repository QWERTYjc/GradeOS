"""Deliver a teacher-selected original-image region without modifying the source."""
import base64
import io
import json
import math
import sys
from PIL import Image

with Image.open(sys.argv[1]) as source:
    rect = json.loads(sys.argv[2])
    width, height = source.size
    box = (max(0, math.floor(rect['x'] * width)), max(0, math.floor(rect['y'] * height)),
           min(width, math.ceil((rect['x'] + rect['width']) * width)),
           min(height, math.ceil((rect['y'] + rect['height']) * height)))
    cropped = source.crop(box)
    if len(sys.argv) > 3:
        max_side = int(sys.argv[3])
        cropped.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    cropped.save(output, format='PNG')
    print(base64.b64encode(output.getvalue()).decode('ascii'))
