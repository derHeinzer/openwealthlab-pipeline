"""Tests for Firestore value conversion helpers."""

from src.shared.firestore_client import _from_firestore_value, _to_firestore_value


class TestToFirestoreValue:
    def test_string(self):
        assert _to_firestore_value("hello") == {"stringValue": "hello"}

    def test_int(self):
        assert _to_firestore_value(42) == {"integerValue": "42"}

    def test_float(self):
        assert _to_firestore_value(3.14) == {"doubleValue": 3.14}

    def test_bool(self):
        assert _to_firestore_value(True) == {"booleanValue": True}


class TestFromFirestoreValue:
    def test_string(self):
        assert _from_firestore_value({"stringValue": "hello"}) == "hello"

    def test_int(self):
        assert _from_firestore_value({"integerValue": "42"}) == 42

    def test_float(self):
        assert _from_firestore_value({"doubleValue": 3.14}) == 3.14

    def test_bool(self):
        assert _from_firestore_value({"booleanValue": True}) is True

    def test_null(self):
        assert _from_firestore_value({"nullValue": None}) is None
