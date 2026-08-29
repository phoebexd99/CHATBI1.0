# Olist 数据接入与 Analytics Mart

## 为什么先选 Olist

Kaggle 的 [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/olistbr/brazilian-ecommerce) 提供约 10 万订单及客户、商品、卖家、支付、评价和物流字段，并明确说明数据已匿名化。Olist 还单独发布 Marketing Funnel，可通过 `seller_id` 与订单侧关联。它适合验证订单经营、履约、客户复购和获客漏斗，但没有真实仓库在手库存流水，因此库存不能用销售量伪造。

TheLook 是很好的第二候选：[GitHub 数据说明](https://github.com/Taweilo/thelook-ecommerce) 展示了 users、orders、order_items、products、inventory_items、events 和 distribution_centers 七张表，覆盖库存和行为分析；但它是 Looker 构造的 fictitious/synthetic 电商数据，不能与 Olist 的匿名商业数据混称为真实库存。

## 分层

```text
Kaggle CSV（本机下载，不进 Git）
        ↓ COPY
chatbi_raw（源表，原始字段保留为 text）
        ↓ 受控转换 / 可审计视图
chatbi_mart.dim_customer / dim_product / dim_seller
chatbi_mart.fct_order / fct_order_item / fct_payment / fct_review
chatbi_mart.fct_marketing_lead
chatbi_mart.fct_inventory_snapshot（等待 WMS/ERP，空表契约）
        ↓
CHATBI 语义目录 / Wren / SQL 安全门
```

## 本地导入

1. 在 Kaggle 下载 Olist 主数据集；如果要做获客漏斗，再下载 Marketing Funnel。解压到本地目录，例如 `D:\data\olist`。原始 CSV 不应提交到 Git。
2. 在本机创建 `.env`，只写本地 SSH 隧道后的 `DATABASE_URL`，不要把密码发到聊天或提交到仓库。隧道约定为 `127.0.0.1:15432`。
3. 首次导入只需要：

```powershell
python -m backend.scripts.load_olist --raw-dir D:\data\olist
```

重复导入必须显式声明 `--replace`，因为它会清空专用 `chatbi_raw` 表后重载。脚本会自动应用 `data/postgres/003_olist_warehouse.sql`，并只加载实际存在的 CSV。

## 接入真实库存快照

Olist 本身没有库存数据。拿到脱敏 WMS/ERP 日快照后，文件至少需要以下字段：`snapshot_date`、`product_key`（或 `product_id`/`sku`）、`available_qty`；可选 `warehouse_key`、`source_record_id`。执行：

```powershell
python -m backend.scripts.load_inventory --csv D:\data\inventory\snapshot.csv --source wms_prod --replace
```

脚本会拒绝负库存、非法日期、空商品键和同一来源下同一商品/仓库/日期重复行；多仓同商品会在写入 `chatbi_mart.fct_inventory_snapshot` 前汇总。每次成功装载都会记录到 `chatbi_meta.data_quality_run`。

## 当前数据边界

- 订单：可认证 `GMV`、订单数、商品数、客单、运费、支付金额、配送时效和评价。
- 历史查询：支持自然语言中的 `2017年11月` 和 `2017-01-01 到 2017-03-31`，适合 Olist 这类历史数据集。
- 营销：可认证 MQL、closed deal、渠道转化和 seller LTV 关联；Olist 没有广告 spend，因此不能把 conversion 当作 ROAS。
- 库存：已建立正式字段契约和导入器，不从订单反推可用库存。要填充它，需要只读 WMS/ERP 快照：`snapshot_date、product_key、available_qty、inventory_source`；当前云端库存行数为 0，等待真实源文件。
- 治理：`chatbi_meta.metric_registry`、`dataset_registry`、`verified_sql` 支持版本、负责人、审核、下线和血缘登记。

## 上云边界

当前迁移只创建 `chatbi_raw`、`chatbi_mart`、`chatbi_meta` 三个新 schema、表、索引和视图，不改现有 `public` 表，不打开防火墙，不部署应用。数据导入前必须先审核 CSV 版本、授权条款、行数和质量检查结果。
