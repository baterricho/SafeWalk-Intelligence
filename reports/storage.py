import mimetypes
import posixpath
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage


class VercelBlobStorage(Storage):
    """Store uploaded report media in Vercel Blob when a token is configured."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = getattr(settings, "BLOB_READ_WRITE_TOKEN", "") or None
        self.local_storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)

    @property
    def using_blob(self):
        return bool(self.token)

    def _open(self, name, mode="rb"):
        return self.local_storage.open(name, mode)

    def _save(self, name, content):
        if not self.using_blob:
            return self.local_storage.save(name, content)

        try:
            from vercel.blob import put
        except ImportError:
            return self.local_storage.save(name, content)

        blob_path = self._unique_blob_path(name)
        content_type = getattr(content, "content_type", None) or mimetypes.guess_type(blob_path)[0]
        body = b"".join(content.chunks()) if hasattr(content, "chunks") else content.read()
        blob = put(
            blob_path,
            body,
            access="public",
            content_type=content_type,
            token=self.token,
            overwrite=False,
        )
        return blob.url

    def delete(self, name):
        if self._is_remote_url(name) and self.using_blob:
            try:
                from vercel.blob import delete

                delete(name, token=self.token)
                return
            except Exception:
                return
        self.local_storage.delete(name)

    def exists(self, name):
        if self._is_remote_url(name) or self.using_blob:
            return False
        return self.local_storage.exists(name)

    def url(self, name):
        if self._is_remote_url(name):
            return name
        return self.local_storage.url(name)

    def size(self, name):
        if self._is_remote_url(name):
            return 0
        return self.local_storage.size(name)

    @staticmethod
    def _is_remote_url(name):
        parsed = urlparse(str(name or ""))
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _unique_blob_path(name):
        directory, filename = posixpath.split(str(name).replace("\\", "/"))
        extension = posixpath.splitext(filename)[1].lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            extension = ".jpg"
        directory = directory.strip("/")
        unique_name = f"{uuid.uuid4().hex}{extension}"
        return posixpath.join(directory, unique_name) if directory else unique_name
