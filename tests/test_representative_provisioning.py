import asyncio

import pytest


@pytest.mark.asyncio
async def test_create_database_grants_application_user(monkeypatch):
    import app.services.representative_provisioner as provisioner

    class FakeCursor:
        def __init__(self):
            self.queries = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, query):
            self.queries.append(query)

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            pass

    fake_connection = FakeConnection()

    class FakeAsyncMy:
        @staticmethod
        async def connect(**kwargs):
            assert kwargs["user"] == "root"
            assert kwargs["database"] == "mysql"
            return fake_connection

    monkeypatch.setenv("MARIADB_ROOT_PASSWORD", "root-secret")
    monkeypatch.setenv("MYSQLHOST_PRIVATE", "mariadb.railway.internal")
    monkeypatch.setenv("MYSQLPORT_PRIVATE", "3306")
    monkeypatch.delenv("MYSQL_ROOT_URL", raising=False)
    monkeypatch.setattr(provisioner.os, "environ", provisioner.os.environ)
    monkeypatch.setattr("asyncmy.connect", FakeAsyncMy.connect)
    monkeypatch.setattr(provisioner, "SQLALCHEMY_DATABASE_URL", "mysql+asyncmy://mariadb:app-pass@mariadb.railway.internal:3306/primevpn")

    await provisioner._create_database("primevpn_rep_2")

    assert fake_connection.cursor_obj.queries[0].startswith("CREATE DATABASE IF NOT EXISTS `primevpn_rep_2`")
    assert "GRANT ALL PRIVILEGES ON `primevpn_rep_2`.* TO 'mariadb'@'%'" in fake_connection.cursor_obj.queries[1]


@pytest.mark.asyncio
async def test_multiple_registrations_are_allowed_after_activation(monkeypatch):
    import app.services.central_registry as registry

    rows = []

    class FakeResult:
        def __init__(self, row=None):
            self._row = row

        def first(self):
            return self._row

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT id FROM bot_registrations" in sql:
                pending = next((r for r in rows if r["owner_user_id"] == params["owner"] and r["status"] in {"draft", "pending", "approved", "provisioning"}), None)
                return FakeResult((pending["id"],) if pending else None)
            if "INSERT INTO bot_registrations" in sql:
                rid = len(rows) + 1
                rows.append({"id": rid, "owner_user_id": params["owner"], "status": "draft"})
                return FakeResult()
            if "SELECT * FROM bot_registrations WHERE owner_user_id" in sql:
                active = [r for r in rows if r["owner_user_id"] == params["owner"] and r["status"] in {"draft", "pending", "approved", "provisioning", "active"}]
                active.sort(key=lambda r: r["id"], reverse=True)
                return FakeResult(type("Row", (), {"_mapping": active[0]})() if active else None)
            if "SELECT id FROM bot_registrations WHERE tracking_code" in sql:
                return FakeResult((rows[-1]["id"],))
            raise AssertionError(f"Unexpected SQL: {sql}")

        async def commit(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(registry, "CentralSessionLocal", lambda: FakeSession())

    rows.append({"id": 1, "owner_user_id": 101, "status": "active"})
    first = await registry.create_draft(101, "PRIME-ONE")
    second = await registry.create_draft(101, "PRIME-TWO")

    assert first == 2
    assert second == 3
