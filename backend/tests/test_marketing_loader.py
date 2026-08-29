import csv

import pytest

from backend.scripts.load_marketing_spend import read_campaign_csv


def test_marketing_loader_accepts_required_fields(tmp_path):
    path = tmp_path / "ads.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric_date", "campaign_id", "channel", "impressions", "clicks", "spend"])
        writer.writeheader()
        writer.writerow({"metric_date": "2026-08-29", "campaign_id": "C-1", "channel": "search", "impressions": "100", "clicks": "8", "spend": "12.5"})
    rows, quality = read_campaign_csv(path, "ads_test")
    assert rows[0]["campaign_key"] == "C-1"
    assert rows[0]["spend"] == "12.5"
    assert quality["row_count"] == 1


def test_marketing_loader_rejects_clicks_above_impressions(tmp_path):
    path = tmp_path / "ads.csv"
    path.write_text("date,campaign,channel,impressions,clicks,spend\n2026-08-29,C-1,search,10,11,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="clicks"):
        read_campaign_csv(path, "ads_test")
