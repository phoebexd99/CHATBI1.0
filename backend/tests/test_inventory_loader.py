import csv

import pytest

from backend.scripts.load_inventory import read_snapshot


def test_inventory_loader_accepts_chinese_aliases_and_aggregates_input_shape(tmp_path):
    path = tmp_path / "inventory.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["快照日期", "商品编码", "可用库存", "仓库编码"])
        writer.writeheader()
        writer.writerow({"快照日期": "2026-08-29", "商品编码": "SKU-1", "可用库存": "7", "仓库编码": "WH-1"})
    rows, quality = read_snapshot(path, "wms_test")
    assert rows[0]["product_key"] == "SKU-1"
    assert rows[0]["available_qty"] == "7"
    assert quality["row_count"] == 1


def test_inventory_loader_rejects_negative_quantity(tmp_path):
    path = tmp_path / "inventory.csv"
    path.write_text("snapshot_date,product_id,available_qty\n2026-08-29,SKU-1,-1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="available_qty"):
        read_snapshot(path, "wms_test")


def test_inventory_loader_rejects_duplicate_product_warehouse_day(tmp_path):
    path = tmp_path / "inventory.csv"
    path.write_text(
        "snapshot_date,product_id,available_qty,warehouse_id\n"
        "2026-08-29,SKU-1,1,WH-1\n"
        "2026-08-29,SKU-1,2,WH-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        read_snapshot(path, "wms_test")
