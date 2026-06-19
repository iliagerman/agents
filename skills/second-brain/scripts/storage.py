#!/usr/bin/env python3
"""storage.py — backend-agnostic file access for the second brain.

The whole brain lives under a single root given by BRAIN_ROOT. The *form* of that
value decides the backend, transparently:

    BRAIN_ROOT=/data/brain                  -> local filesystem
    BRAIN_ROOT=s3://my-bucket/brain         -> S3 (boto3)

Everything else in the skill works in **brain-relative POSIX paths**
(e.g. "personal/travel/index.md"); this module maps them to a local path or an
S3 key. Nothing above this module knows which backend is in use.

Optional for S3 (custom endpoints — s3-compatible stores, LocalStack, etc.):
    BRAIN_S3_ENDPOINT_URL=http://localhost:4566
    AWS_REGION / standard AWS credential chain
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


def _die(msg: str) -> None:
    print(f"storage: {msg}", file=sys.stderr)
    sys.exit(2)


def brain_root() -> str:
    root = os.environ.get("BRAIN_ROOT", "").strip()
    if root:
        return root
    return str(Path.home() / "second_brain")


def get_storage(root: str | None = None) -> "Storage":
    """Return the right backend based on the shape of BRAIN_ROOT."""
    root = root or brain_root()
    if root.startswith("s3://"):
        return S3Storage(root)
    return LocalStorage(root)


@dataclass
class Listing:
    """Immediate children of a cluster directory."""
    clusters: list[str]   # sub-directory names that are clusters (contain index.md)
    notes: list[str]      # *.md filenames other than index.md


class Storage:
    """Interface. All paths are brain-relative POSIX strings; "" is the root."""

    backend: str = "?"

    def exists(self, rel: str) -> bool: raise NotImplementedError
    def read_text(self, rel: str) -> str: raise NotImplementedError
    def write_text(self, rel: str, content: str) -> None: raise NotImplementedError
    def delete(self, rel: str) -> None: raise NotImplementedError
    def list_dir(self, rel: str = "") -> Listing: raise NotImplementedError
    def walk_md(self) -> list[str]: raise NotImplementedError  # all .md, brain-relative

    # Binary / attachment access — for note attachments (images, PDFs, …).
    def read_bytes(self, rel: str) -> bytes: raise NotImplementedError
    def write_bytes(self, rel: str, data: bytes) -> None: raise NotImplementedError
    def list_files(self, rel: str) -> list[str]:  # immediate file names in a dir
        raise NotImplementedError
    def delete_prefix(self, rel: str) -> None:  # delete a folder + everything in it
        raise NotImplementedError

    # Shared helpers ---------------------------------------------------------
    @staticmethod
    def _join(parent: str, name: str) -> str:
        parent = parent.strip("/")
        return f"{parent}/{name}" if parent else name

    def is_cluster(self, rel: str) -> bool:
        """A directory is a cluster iff it holds an index.md."""
        return self.exists(self._join(rel, "index.md"))


# --------------------------------------------------------------------------- #
# Local filesystem
# --------------------------------------------------------------------------- #
class LocalStorage(Storage):
    backend = "local"

    def __init__(self, root: str):
        from pathlib import Path

        self._Path = Path
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, rel: str):
        p = (self.root / rel).resolve()
        # Guard against path traversal escaping the brain.
        if self.root not in p.parents and p != self.root:
            _die(f"path {rel!r} escapes BRAIN_ROOT")
        return p

    def exists(self, rel: str) -> bool:
        return self._abs(rel).exists()

    def read_text(self, rel: str) -> str:
        return self._abs(rel).read_text(encoding="utf-8")

    def write_text(self, rel: str, content: str) -> None:
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        p = self._abs(rel)
        if p.is_file():
            p.unlink()

    def list_dir(self, rel: str = "") -> Listing:
        base = self._abs(rel) if rel else self.root
        clusters, notes = [], []
        if not base.is_dir():
            return Listing([], [])
        for child in sorted(base.iterdir()):
            if child.is_dir():
                if (child / "index.md").exists():
                    clusters.append(child.name)
            elif child.suffix == ".md" and child.name != "index.md":
                notes.append(child.name)
        return Listing(clusters, notes)

    def walk_md(self) -> list[str]:
        out = []
        for p in sorted(self.root.rglob("*.md")):
            out.append(p.relative_to(self.root).as_posix())
        return out

    def read_bytes(self, rel: str) -> bytes:
        return self._abs(rel).read_bytes()

    def write_bytes(self, rel: str, data: bytes) -> None:
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def list_files(self, rel: str) -> list[str]:
        base = self._abs(rel) if rel else self.root
        if not base.is_dir():
            return []
        return sorted(c.name for c in base.iterdir() if c.is_file())

    def delete_prefix(self, rel: str) -> None:
        p = self._abs(rel)
        if p.is_dir():
            shutil.rmtree(p)


# --------------------------------------------------------------------------- #
# S3 (boto3). Directories are implicit; a cluster exists when its index.md key
# exists. Listing uses Delimiter="/" to get CommonPrefixes (sub-dirs).
# --------------------------------------------------------------------------- #
class S3Storage(Storage):
    backend = "s3"

    def __init__(self, root: str):
        try:
            import boto3
        except ImportError:  # pragma: no cover - dependency guard
            _die("S3 root requires boto3. Run `pip install boto3`.")
        rest = root[len("s3://"):]
        self.bucket, _, prefix = rest.partition("/")
        if not self.bucket:
            _die(f"malformed S3 root {root!r}; expected s3://bucket[/prefix]")
        self.prefix = prefix.strip("/")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("BRAIN_S3_ENDPOINT_URL") or None,
            region_name=os.environ.get("AWS_REGION") or None,
        )

    def _key(self, rel: str) -> str:
        rel = rel.strip("/")
        return f"{self.prefix}/{rel}" if self.prefix else rel

    def _rel(self, key: str) -> str:
        if self.prefix and key.startswith(self.prefix + "/"):
            return key[len(self.prefix) + 1:]
        return key

    def exists(self, rel: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._s3.head_object(Bucket=self.bucket, Key=self._key(rel))
            return True
        except ClientError:
            return False

    def read_text(self, rel: str) -> str:
        obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(rel))
        return obj["Body"].read().decode("utf-8")

    def write_text(self, rel: str, content: str) -> None:
        self._s3.put_object(
            Bucket=self.bucket, Key=self._key(rel),
            Body=content.encode("utf-8"), ContentType="text/markdown",
        )

    def delete(self, rel: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=self._key(rel))

    def list_dir(self, rel: str = "") -> Listing:
        prefix = self._key(rel)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        clusters, notes = [], []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                name = cp["Prefix"][len(prefix):].strip("/")
                if name and self.is_cluster(self._join(rel, name)):
                    clusters.append(name)
            for obj in page.get("Contents", []):
                name = obj["Key"][len(prefix):]
                if "/" in name:
                    continue
                if name.endswith(".md") and name != "index.md":
                    notes.append(name)
        return Listing(sorted(clusters), sorted(notes))

    def walk_md(self) -> list[str]:
        prefix = self.prefix + "/" if self.prefix else ""
        out = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".md"):
                    out.append(self._rel(obj["Key"]))
        return sorted(out)

    def read_bytes(self, rel: str) -> bytes:
        obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(rel))
        return obj["Body"].read()

    def write_bytes(self, rel: str, data: bytes) -> None:
        content_type = mimetypes.guess_type(rel)[0] or "application/octet-stream"
        self._s3.put_object(
            Bucket=self.bucket, Key=self._key(rel),
            Body=data, ContentType=content_type,
        )

    def list_files(self, rel: str) -> list[str]:
        prefix = self._key(rel)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        names: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for obj in page.get("Contents", []):
                name = obj["Key"][len(prefix):]
                if name and "/" not in name:
                    names.append(name)
        return sorted(names)

    def delete_prefix(self, rel: str) -> None:
        prefix = self._key(rel)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        to_delete: list[dict[str, str]] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                to_delete.append({"Key": obj["Key"]})
        for i in range(0, len(to_delete), 1000):
            self._s3.delete_objects(
                Bucket=self.bucket, Delete={"Objects": to_delete[i:i + 1000]}
            )


if __name__ == "__main__":
    s = get_storage()
    print(f"backend={s.backend} root={brain_root()}")
    print("top-level:", s.list_dir(""))
