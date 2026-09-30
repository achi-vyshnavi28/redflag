"""Memo storage on AWS S3 (tested against moto's local S3) and the local fallback."""
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from redflag.storage import LocalStore, S3Store, get_store

NOW = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def s3(monkeypatch):
    for k, v in {"AWS_DEFAULT_REGION": "ap-south-1", "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing"}.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="redflag-memos", CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
        yield client


def test_s3_put_is_encrypted_typed_and_keyed(s3):
    out = S3Store("redflag-memos", client=s3).put_memo("madhur_steel", "# Memo\nreceivables up 92%", now=NOW)
    assert out["uri"] == "s3://redflag-memos/memos/madhur_steel/20261001T093000Z.md"
    head = s3.head_object(Bucket="redflag-memos", Key=out["key"])
    assert head["ServerSideEncryption"] == "AES256"
    assert head["ContentType"].startswith("text/markdown")
    assert head["Metadata"]["doc"] == "madhur_steel"
    assert "X-Amz-Expires=3600" in out["url"]


def test_s3_list_by_document(s3):
    store = S3Store("redflag-memos", client=s3)
    store.put_memo("atomberg", "a", now=NOW)
    store.put_memo("madhur_steel", "b", now=NOW)
    assert store.list_memos("atomberg") == ["memos/atomberg/20261001T093000Z.md"]


def test_local_fallback_and_env_switch(tmp_path, monkeypatch):
    store = LocalStore(tmp_path)
    out = store.put_memo("atomberg", "# Memo", now=NOW)
    assert (tmp_path / out["key"]).read_text(encoding="utf-8") == "# Memo"
    assert store.list_memos("atomberg") == [out["key"]]
    monkeypatch.delenv("REDFLAG_S3_BUCKET", raising=False)
    assert isinstance(get_store(), LocalStore)
