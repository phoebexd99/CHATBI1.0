# 开源数据源与可接入边界

## 结论

可以找到公开脱敏或合成的电商数据，但目前没有找到一套同时满足以下条件、且可以无歧义拼接进 Olist 的单一数据源：

1. 订单、商品、客户、营销投放和仓库在手库存同时存在；
2. 各域之间有稳定的业务主键和可解释的归因关系；
3. 可以长期、合规、无需人工登录地重复下载。

因此当前采用“主数据集 + 独立域快照契约”的方式：Olist 负责订单经营主链路，WMS/ERP 和广告平台导出分别进入独立事实表。不同数据集之间不强行拼接匿名 ID，也不把需求预测数据解释成实际库存。

## 数据源对比

| 数据源 | 能提供的业务域 | 数据性质 | 能否直接接入当前项目 | 主要限制 |
| --- | --- | --- | --- | --- |
| [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/olistbr/brazilian-ecommerce) | 订单、订单明细、客户、商品、卖家、支付、评价、配送；另有 Marketing Funnel | 公开匿名商业数据 | **已接入**云端 Olist warehouse | 没有仓库在手库存、广告 spend、退款流水；无法直接发布真实 ROAS 或库存周转 |
| [TheLook eCommerce](https://github.com/Taweilo/thelook-ecommerce) | users、orders、order_items、products、inventory_items、events、distribution_centers | Looker 构造的 fictitious/synthetic 数据 | 可作为独立 `thelook` benchmark，或映射到通用 loader | 独立匿名/合成主键；`inventory_items` 是商品实例生命周期，不等于 WMS 每日 on-hand 快照；不能与 Olist 订单直接关联 |
| [dunnhumby Complete Journey](https://www.dunnhumby.com/wp-content/uploads/2023/08/Let_s-Get-Sort-of-Real-User-Guide-dunnhumby.pdf) | 交易、家庭画像、优惠券、促销活动、优惠券核销 | 官方 dummy/研究数据 | 可作为独立营销/促销 benchmark | 不是 Olist 订单；没有仓库库存和广告媒体 spend；需要单独的 household/product 语义目录 |
| [Criteo Research Datasets](https://ailab.criteo.com/ressources/) | 匿名广告展示、点击、访问、转化或 uplift 标签 | 真实业务日志的匿名研究集 | 可用于广告/归因算法评测，不能直接填充 Olist 的 campaign fact | 关键字段经过匿名化或特征投影；不同数据集的归因粒度、成本字段和授权条款不同；没有 Olist `order_id` |

## 当前已完成的接入

云端 PostgreSQL 已加载 Olist 的源表和 Mart 视图：

- `chatbi_raw`：customers、orders、order_items、payments、reviews、products、sellers、category translation、Marketing Funnel；
- `chatbi_mart`：`dim_customer`、`dim_product`、`dim_seller`、`fct_order`、`fct_order_item`、`fct_payment`、`fct_review`、`fct_marketing_lead`；
- `chatbi_meta`：数据集登记、指标登记、Verified SQL 和数据质量审计；
- 已支持 Olist GMV、有效订单、客单、购买客户、MQL、线索转化率等语义查询和历史日期过滤。

原始 CSV 只保存在本地忽略目录，不进入 Git，也不把 Kaggle 凭证或数据库口令写入项目。

## 为什么暂不自动导入 TheLook 或广告数据

自动导入一个主键体系不同、授权或下载稳定性尚未确认的数据，会让回答看起来更丰富，但会产生错误的跨域结论。例如，把 TheLook 的 `inventory_items` 与 Olist 的商品销售量相加，或把 Criteo 的匿名 conversion 当成 Olist 订单归因，都会让库存、ROAS 和转化率失去业务含义。

当前仓库已经为两个真实入口准备了正式契约：

```text
脱敏 WMS/ERP CSV
  → backend.scripts.load_inventory
  → chatbi_raw.wms_inventory_snapshot
  → chatbi_mart.fct_inventory_snapshot

广告平台/脱敏数仓 CSV
  → backend.scripts.load_marketing_spend
  → chatbi_raw.ad_campaign_daily
  → chatbi_mart.fct_marketing_daily
```

库存文件至少需要 `snapshot_date、product_key、available_qty`；广告文件至少需要 `metric_date、campaign_key、channel、spend`。导入器会校验日期、空键、负数、重复粒度和点击/曝光关系，并记录 `chatbi_meta.data_quality_run`。

## 推荐深入路径

### 作品集演示路径

保留 Olist 作为主 profile；如果需要展示库存/行为，可以将 TheLook 单独导出一份小型、带来源标记的 benchmark profile。它只能回答“合成库存生命周期/行为数据上的问题”，页面和 Trace 必须明确标注数据集，不与 Olist 指标混算。

### 业务可用路径

优先获得一份脱敏 WMS/ERP 日快照和一份广告平台日汇总。两者不需要暴露 PII，但必须保留：

- 商品或 SKU 的稳定映射键；
- 仓库、渠道、活动的业务键；
- 业务日期、时区、币种；
- 归因窗口和归因模型；
- 变更/重跑标识及数据负责人。

拿到文件后，先在 staging 做行数、唯一性、主外键、日期覆盖和总额对账，再发布为正式 Mart 和认证指标。

### 当前能力边界

- Olist 可以支撑订单经营、履约时效、评价和营销线索漏斗；
- 当前不能从公开 Olist 推导真实可售库存、缺货率、库存周转或补货建议；
- 当前不能从 Olist 发布广告 spend、真实 ROAS 或跨平台归因；
- TheLook、dunnhumby、Criteo 若接入，应作为独立数据 profile，而不是与 Olist 匿名键硬连接；
- pgvector、生产级 Wren、认证/RLS、可观测性和真实业务 100 题验收仍属于后续建设。

