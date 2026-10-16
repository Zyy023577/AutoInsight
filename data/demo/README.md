# Demo 数据说明

`cars.json` 是 AutoInsight 第一阶段的人工构造演示数据，不代表任何真实汽车品牌、车型、价格、续航、配置或用户观点，也不能用于市场结论。

每条记录包含 `source_name`、`source_url`、`collected_at`、`data_status` 和 `source_type` 字段；`opinions` 中的观点也明确标记了合成来源和采集日期。后续接入获得授权的公开数据时，应保留原始来源、采集日期和适用版本，并将 `data_status` 改为经过核验的状态。
