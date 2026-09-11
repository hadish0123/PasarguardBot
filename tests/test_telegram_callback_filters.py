import re
from types import SimpleNamespace

from telethon import events


def test_callback_query_exact_bytes_filter():
    builder = events.CallbackQuery(data=b"central:admin:approve:42")
    event = SimpleNamespace(data=b"central:admin:approve:42")
    assert builder.matches(event)


def test_callback_query_regex_filter():
    builder = events.CallbackQuery(data=re.compile(rb"^central:admin:"))
    event = SimpleNamespace(data=b"central:admin:approve:42")
    assert builder.matches(event)


def test_callback_query_regex_rejects_other_namespace():
    builder = events.CallbackQuery(data=re.compile(rb"^central:admin:"))
    event = SimpleNamespace(data=b"central:user:home")
    assert not builder.matches(event)
