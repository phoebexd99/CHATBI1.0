# 真实业务问题采集与 Golden/Holdout

当前项目已有 45 条开发集 Golden 问题，但它们不是从真实业务人员访谈中采集的，不能替代正式验收集。真实问题应由运营、市场、商品、供应链和财务人员填写 [采集模板](../evals/business_question_intake_template.csv)，至少记录：问题原文、业务角色、指标/维度、时间范围、期望输出、数据口径备注和审核状态。

提交前必须将 `review_status` 改为 `approved`，删除模板中的示例行，并补齐至少 100 条去重问题。执行：

```powershell
python -m backend.scripts.split_evaluations --input evals\business_questions.csv --golden-output evals\golden_100.json --holdout-output evals\holdout_100.json
```

脚本按 `expected + metric` 分层，以稳定哈希抽取约 20% Holdout，避免依赖 CSV 行顺序。Golden 用于迭代，Holdout 只在发布前或重大语义变更后评估。相似改写问题不能同时跨 Golden/Holdout，否则会高估泛化能力。

真实问题采集完成前，项目只能报告当前 45 条开发集结果，不能声称完成“100 条真实业务验收”。
