"""Private photo storage and a bounded decoder that discards uploaded metadata."""
from io import BytesIO
import os
import warnings
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from PIL import Image, ImageOps, UnidentifiedImageError


@deconstructible
class PrivatePhotoStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Student photos must be served through the authorized photo view.")


photo_storage = PrivatePhotoStorage()


def photo_path(instance, filename):
    return f"students/{uuid4().hex}.jpg"


def clean_photo(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("Choose a photo smaller than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Choose a JPEG, PNG or WebP photo.")
                if source.width * source.height > 16_000_000:
                    raise ValidationError("Choose a photo with at most 16 million pixels.")
                source.load()
                picture = ImageOps.exif_transpose(source).convert("RGB")
                picture.thumbnail((1600, 1600))
                # A fresh image prevents EXIF, comments and trailing data being copied.
                clean = Image.new("RGB", picture.size)
                clean.paste(picture)
                output = BytesIO()
                clean.save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError("Upload a valid, undamaged photo.") from None
    finally:
        upload.seek(0)
    return ContentFile(output.getvalue(), name="photo.jpg")
