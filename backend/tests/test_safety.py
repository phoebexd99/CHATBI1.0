import pytest

from backend.app.safety import SQLSafetyGate, UnsafeSQL


def test_accepts_allowlisted_select():
    sql = SQLSafetyGate().validate("SELECT SUM(gross_amount) AS gmv FROM orders", "sqlite")
    assert "orders" in sql.lower()


@pytest.mark.parametrize("sql", [
    "DELETE FROM orders", "SELECT * FROM sqlite_master", "SELECT 1; SELECT 2", "SELECT * FROM orders -- bypass"
])
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQL):
        SQLSafetyGate().validate(sql, "sqlite")

