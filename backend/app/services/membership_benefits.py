"""会员页对比表（方案 5.6）。小程序内只展示权益，不出现价格和购买入口。Max 第二期上线。"""

BENEFITS = {
    "tiers": [
        {"code": "free", "name": "免费"},
        {"code": "pro", "name": "Pro"},
        {"code": "max", "name": "Max", "coming_soon": True},
    ],
    "rows": [
        {"key": "food", "label": "拍食物识别", "free": "3 次/天", "pro": "30 次/天", "max": "不限"},
        {"key": "inbody", "label": "拍 InBody 报告", "free": "1 次/月", "pro": "不限", "max": "不限"},
        {"key": "interpret", "label": "指标解读", "free": "色条与上次对比", "pro": "+ AI 文字解读", "max": "+ AI 阶段建议"},
        {"key": "plans", "label": "饮食挑战", "free": "看点亮", "pro": "+ 原因和替换建议", "max": "+ 自定义挑战"},
        {"key": "routines", "label": "规律小事", "free": "3 件", "pro": "不限", "max": "不限 + 家人共享"},
        {"key": "history", "label": "历史曲线", "free": "最近 90 天", "pro": "全部", "max": "全部"},
        {"key": "export", "label": "数据导出", "free": "—", "pro": "表格", "max": "表格 + PDF 报告"},
        {"key": "manual", "label": "手动记录", "free": "不限", "pro": "不限", "max": "不限"},
    ],
}
