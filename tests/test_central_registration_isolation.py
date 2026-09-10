import asyncio

import pytest


@pytest.mark.asyncio
async def test_two_users_keep_independent_registration_ids(monkeypatch):
    registrations = {
        101: {"id": 1, "owner_user_id": 101, "status": "draft", "step": "bot_token", "bot_id": None},
        202: {"id": 2, "owner_user_id": 202, "status": "draft", "step": "bot_token", "bot_id": None},
    }

    async def get_active_for_owner(user_id):
        return registrations[user_id]

    async def get_by_id(registration_id):
        return next((r for r in registrations.values() if r["id"] == registration_id), None)

    async def get_by_bot_id(_bot_id):
        return None

    async def update_registration(registration_id, **values):
        row = await get_by_id(registration_id)
        row.update(values)

    async def fake_get_me(token):
        if token == "TOKEN_A":
            await asyncio.sleep(0.01)
            return {"id": 111, "username": "token_a"}
        await asyncio.sleep(0)
        return {"id": 222, "username": "token_b"}

    monkeypatch.setattr("app.telegram.admin.central_registration.get_active_for_owner", get_active_for_owner)
    monkeypatch.setattr("app.telegram.admin.central_registration.get_by_id", get_by_id)
    monkeypatch.setattr("app.telegram.admin.central_registration.get_by_bot_id", get_by_bot_id)
    monkeypatch.setattr("app.telegram.admin.central_registration.update_registration", update_registration)
    monkeypatch.setattr("app.telegram.admin.central_registration._get_me", fake_get_me)
    monkeypatch.setattr("app.telegram.admin.central_registration.protect", lambda value: f"protected:{value}")

    class Event:
        def __init__(self, sender_id, raw_text):
            self.sender_id = sender_id
            self.raw_text = raw_text
            self.responses = []

        async def respond(self, text):
            self.responses.append(text)

    from app.telegram.admin.central_registration import registration_messages

    await asyncio.gather(
        registration_messages(Event(101, "TOKEN_A")),
        registration_messages(Event(202, "TOKEN_B")),
    )

    assert registrations[101]["bot_id"] == 111
    assert registrations[202]["bot_id"] == 222
    assert registrations[101]["bot_id"] != registrations[202]["bot_id"]
    assert registrations[101]["step"] == "bot_id"
    assert registrations[202]["step"] == "bot_id"
    assert registrations[101]["bot_token"] == "protected:TOKEN_A"
    assert registrations[202]["bot_token"] == "protected:TOKEN_B"
