# 数据可视化与图片内容模块（3.6 系统实现）

> 对应课程进度清单 3.6「企业数据可视化面板」。
> 按用户要求：只改代码与页面，**不再回头改前面 Word 文档的内容**。

## 一、做了什么

| 模块 | 页面 | 说明 |
| --- | --- | --- |
| 企业数据可视化 | `/chart/enterprise/` | 经营状态饼图、注册资本区间柱图、成立年份分布 |
| 风险数据可视化 | `/chart/risk/` | 风险等级饼图、得分分布柱图、得分 Top10 表 |
| 图片内容模块 | `/chart/image/<kind>.svg` | 服务端实时生成 SVG 图片，可嵌入页面或加 `?download=1` 下载 |

`kind` 取值：`status`、`capital`、`year`、`level`、`score`。

## 二、实现方式

- **不依赖 CDN / 前端图表库**：`risk_app/charts.py` 用纯 Python 拼 SVG（柱状、饼图、直方图），离线也能显示；
- 数据实时来自 MySQL，不写死：企业 10000 条、风险 10000 条；
- 图表页面同时是图片页面：`<img src="/chart/image/status.svg">`，右键或“下载 SVG”即可拿到矢量图；
- 字体与配色沿用项目规范（Times New Roman + SimSun，低饱和五色）。

## 三、文件

| 文件 | 作用 |
| --- | --- |
| `risk_app/charts.py` | SVG 图表生成（bar_chart / pie_chart / hist_chart） |
| `risk_app/views.py` | `chart_enterprise`、`chart_risk`、`chart_image` 三个视图 |
| `risk_app/urls.py` | 三条路由 |
| `risk_app/templates/chart_enterprise.html` | 企业可视化页面 |
| `risk_app/templates/chart_risk.html` | 风险可视化页面 |
| `截图/企业数据可视化.png`、`风险数据可视化.png` | 运行截图 |

## 四、验证

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8010/chart/enterprise/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8010/chart/image/status.svg
```

当前结果：页面 200，SVG 200；企业 10000、在营 6146 / 注销 2687 / 吊销 1167；风险平均分 35.17、最高 88.67（百分制，0–100）。

## 五、后续

- 报告页（3.4）引用这些 SVG，作为报告配图；
- 图表筛选（按年份、状态联动）留到项目 10/11；
- 大模型预估（3.5）单独接，不在此模块内。