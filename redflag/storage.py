"""Where generated memos are kept: a local folder by default, or AWS S3 when REDFLAG_S3_BUCKET is set.

S3 objects are written with server-side encryption and a content type, keyed by document and time
(memos/<doc>/<UTC timestamp>.md), and shared through short-lived presigned URLs rather than public buckets.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from redflag.config import REPORTS


def _key(doc: str, now: datetime | None = None) -> str:
    return f"memos/{doc}/{(now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')}.md"


class LocalStore:
    def __init__(self, root: Path = REPORTS / "artifacts"):
        self.root = root

    def put_memo(self, doc: str, markdown: str, now: datetime | None = None) -> dict:
        path = self.root / _key(doc, now)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return {"uri": path.as_uri(), "key": _key(doc, now)}

    def list_memos(self, doc: str) -> list[str]:
        folder = self.root / "memos" / doc
        return sorted(f"memos/{doc}/{p.name}" for p in folder.glob("*.md")) if folder.exists() else []


class S3Store:
    def __init__(self, bucket: str, client=None):
        import boto3

        self.bucket = bucket
        self.s3 = client or boto3.client("s3")

    def put_memo(self, doc: str, markdown: str, now: datetime | None = None) -> dict:
        key = _key(doc, now)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=markdown.encode("utf-8"),
                           ContentType="text/markdown; charset=utf-8", ServerSideEncryption="AES256",
                           Metadata={"doc": doc})
        url = self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=3600)
        return {"uri": f"s3://{self.bucket}/{key}", "key": key, "url": url}

    def list_memos(self, doc: str) -> list[str]:
        r = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=f"memos/{doc}/")
        return sorted(o["Key"] for o in r.get("Contents", []))


def get_store():
    bucket = os.getenv("REDFLAG_S3_BUCKET")
    return S3Store(bucket) if bucket else LocalStore()
