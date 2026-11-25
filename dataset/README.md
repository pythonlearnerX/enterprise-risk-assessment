# dataset（实训数据集目录）

> 数据已到位（2026-11-02），按指导书结构放置，文件名保持老师原样。

## 实际文件

| 文件 | 规模 | 说明 |
| --- | --- | --- |
| `dwd_essential_info_commercial_.csv` | 10000 行 × 59 列（4.68 MB） | 企业工商注册明细，UTF-8 |
| `ads_company_rating_basis_1w.csv` | 10000 行 × 19 列（5.69 MB） | 风险评级基础（12 项指标），UTF-8 |
| `dwd_essential_info_commercial_sample.csv` | 10 行 × 59 列 | **本项目生成**：取全量前 10 行，供脚本默认 `use_sample=True` 使用 |
| `ads_company_rating_basis_sample.csv` | 10 行 × 19 列 | **本项目生成**：同上 |
| `企业基本信息字段定义.xlsx` | 59 个字段 | 字段名、含义、类型、示例 |
| `企业基准风险信息字段表.xlsx` | 19 个字段 | 同上，含 12 项指标含义 |

## 与指导书的差异（已确认）

1. 企业表实际文件名被截断为 `..._commercial_.csv`，指导书写 `..._commercial_reg_info.csv`，示例代码又写 `..._1w.csv`——**以本目录实际文件名为准**，脚本里统一定义常量。
2. 老师没有给 `*_sample.csv`，本项目用全量前 10 行生成，结构与全量一致。
3. 企业表注册资本字段名是 `reg_cap`（单位万元），**不是** `zhuce_money`；`zhuce_money` 只在风险表出现。
4. 两张表都带 `id` / `id_num`：企业表 `id`、`firm_eid` 与风险表 `id` 可关联。

## 注意

- 数据为脱敏数据，仅用于本课程，不得外传。
- 本目录只放原始数据与样本；清洗结果、统计输出放项目 `outputs/`。
- 数据文件已在项目 `.gitignore` 中排除（`dataset/*.csv`、`dataset/*.xlsx`），不随代码入库。