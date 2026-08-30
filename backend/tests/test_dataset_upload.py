from io import BytesIO

from openpyxl import Workbook

from backend.app.datasets import DatasetService, UploadedDatasetAnalyzer


def test_csv_upload_profiles_data_and_answers_dynamic_question(tmp_path):
    service = DatasetService(tmp_path / "datasets.db")
    dataset = service.upload(
        "sales.csv",
        "日期,地区,销售额\n2026-01-01,华东,120\n2026-01-02,华南,90\n2026-01-03,华东,180\n".encode("utf-8"),
        "销售数据",
    )

    assert dataset["source_type"] == "csv"
    assert dataset["row_count"] == 3
    assert dataset["tables"][0]["columns"][0]["type"] == "date"
    assert dataset["tables"][0]["columns"][2]["type"] == "integer"
    assert "按地区统计销售额合计" in dataset["suggestions"]

    result = UploadedDatasetAnalyzer(service).run(dataset["id"], "按地区统计销售额合计")
    assert result["columns"] == ["地区", "销售额合计"]
    assert result["rows"][0] == ["华东", 300]
    assert result["chart_spec"]["type"] == "bar"
    assert result["evidence"][0]["type"] == "dataset_schema"


def test_xlsx_upload_keeps_multiple_sheets_and_generates_preview(tmp_path):
    workbook = Workbook()
    orders = workbook.active
    orders.title = "订单"
    orders.append(["订单日期", "渠道", "金额"])
    orders.append(["2026-01-01", "小程序", 199.5])
    orders.append(["2026-01-02", "门店", 280])
    customers = workbook.create_sheet("客户")
    customers.append(["客户", "区域"])
    customers.append(["客户A", "华东"])
    buffer = BytesIO()
    workbook.save(buffer)

    service = DatasetService(tmp_path / "datasets.db")
    dataset = service.upload("经营数据.xlsx", buffer.getvalue())

    assert dataset["source_type"] == "excel"
    assert dataset["table_count"] == 2
    assert dataset["row_count"] == 3
    assert dataset["tables"][0]["sheet_name"] == "订单"
    assert dataset["tables"][0]["preview"][0]["渠道"] == "小程序"


def test_dataset_list_always_keeps_ecommerce_demo_template(tmp_path):
    service = DatasetService(tmp_path / "datasets.db")
    items = service.list_datasets()

    assert items[0]["id"] == "demo"
    assert items[0]["source_type"] == "template"
    assert "电商" in items[0]["name"]
