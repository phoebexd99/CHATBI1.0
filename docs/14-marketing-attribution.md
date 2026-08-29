# 广告 spend 与归因接入

Olist Marketing Funnel 可以支持 MQL、Closed Deal 和渠道转化，但不提供广告曝光、点击、花费和归因收入。因此当前不能从 Olist 直接发布真实 ROAS。

本项目新增：

- `chatbi_raw.ad_campaign_daily`：保留广告平台日数据；
- `chatbi_mart.fct_marketing_daily`：正式 spend/归因事实，按日期、活动、渠道、来源去重；
- `chatbi_meta.data_quality_run`：记录每次导入的行数和校验结果；
- `backend/scripts/load_marketing_spend.py`：校验并装载脱敏广告导出。

最小字段：`metric_date`、`campaign_key`、`channel`、`spend`。建议同时提供 `impressions`、`clicks`、`sessions`、`attributed_orders`、`attributed_revenue`，并在导入前确认归因窗口、归因模型、币种和时区。

```powershell
python -m backend.scripts.load_marketing_spend --csv D:\data\ads\daily.csv --source ads_prod --replace
```

在业务审核通过前，`spend` 和 `attributed_revenue` 只能作为待认证数据；不能把 Olist 的线索转化率与广告 ROAS 混用。下一步应接入一个只读广告平台导出或脱敏数仓表，再将 `fct_marketing_daily` 注册为版本化指标。

真实广告数据接入后，必须固定归因窗口、归因模型、币种和时区，并至少用一个历史月份做回算校验，确认广告平台汇总与 Mart 汇总一致后再发布 ROAS。
