from pathlib import Path

from django.core.exceptions import ValidationError


MAX_PRIVATE_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_UPLOADS = {
    ".pdf": ("application/pdf", lambda header: header.startswith(b"%PDF-")),
    ".jpg": ("image/jpeg", lambda header: header.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda header: header.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda header: header.startswith(b"\x89PNG\r\n\x1a\n")),
}


def validate_private_upload(upload):
    if upload.size > MAX_PRIVATE_UPLOAD_SIZE:
        raise ValidationError("El archivo no puede superar 5 MB.")

    extension = Path(upload.name).suffix.lower()
    expected = ALLOWED_UPLOADS.get(extension)
    if not expected:
        raise ValidationError("Solo se permiten archivos PDF, JPG y PNG.")

    content_type, matches_signature = expected
    if getattr(upload, "content_type", "") != content_type:
        raise ValidationError("El tipo del archivo no coincide con su extensión.")

    position = upload.tell()
    header = upload.read(8)
    upload.seek(position)
    if not matches_signature(header):
        raise ValidationError("El contenido del archivo no coincide con el formato indicado.")

    return upload
