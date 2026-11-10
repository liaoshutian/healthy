"""规律生活模板、身体部位（三级）、症状标签。小程序也会从 /api/meta 拉这些数据。"""

ROUTINE_TEMPLATES = [
    {"name": "理发", "icon": "✂️", "cycle_days": 28, "remind_days_before": 2},
    {"name": "换牙刷", "icon": "🪥", "cycle_days": 90, "remind_days_before": 3},
    {"name": "洗牙", "icon": "🦷", "cycle_days": 180, "remind_days_before": 7},
    {"name": "体检", "icon": "🩺", "cycle_days": 365, "remind_days_before": 14},
    {"name": "换床单", "icon": "🛏️", "cycle_days": 14, "remind_days_before": 1},
    {"name": "剪指甲", "icon": "💅", "cycle_days": 7, "remind_days_before": 1},
    {"name": "换隐形眼镜", "icon": "👁️", "cycle_days": 30, "remind_days_before": 2},
    {"name": "猫狗驱虫", "icon": "🐾", "cycle_days": 90, "remind_days_before": 3},
    {"name": "献血", "icon": "🩸", "cycle_days": 180, "remind_days_before": 7},
    {"name": "换滤芯", "icon": "💧", "cycle_days": 180, "remind_days_before": 7},
]

SYMPTOM_TAGS = ["疼痛", "酸胀", "发热", "咳嗽", "流涕", "咽痛", "头晕", "恶心", "腹泻", "便秘", "过敏", "瘙痒", "失眠", "乏力", "抽筋", "肿胀"]


def _p(code, label, children=None, side="both"):
    node = {"code": code, "label": label, "side": side}
    if children:
        node["children"] = children
    return node


# 三级部位：大部位 → 局部 → 更细的位置。side 表示在人体图正面(front)/背面(back)/两面(both)出现。
BODY_PARTS = [
    _p("head", "头部", [
        _p("head.forehead", "前额", side="front"),
        _p("head.temple", "太阳穴", [_p("head.temple.l", "左太阳穴"), _p("head.temple.r", "右太阳穴")]),
        _p("head.top", "头顶"),
        _p("head.back", "后脑", side="back"),
        _p("head.eye", "眼睛", [_p("head.eye.l", "左眼"), _p("head.eye.r", "右眼"), _p("head.eye.orbit", "眼眶")], side="front"),
        _p("head.ear", "耳朵", [_p("head.ear.l", "左耳"), _p("head.ear.r", "右耳")]),
        _p("head.nose", "鼻子", side="front"),
        _p("head.mouth", "口腔", [_p("head.mouth.tooth", "牙齿"), _p("head.mouth.gum", "牙龈"), _p("head.mouth.tongue", "舌头")], side="front"),
    ]),
    _p("neck", "颈部", [
        _p("neck.throat", "咽喉", [_p("neck.throat.upper", "上部"), _p("neck.throat.lower", "下部"), _p("neck.throat.l", "左侧"), _p("neck.throat.r", "右侧")], side="front"),
        _p("neck.nape", "后颈", side="back"),
    ]),
    _p("chest", "胸部", [_p("chest.l", "左胸"), _p("chest.r", "右胸"), _p("chest.center", "胸口正中")], side="front"),
    _p("abdomen", "腹部", [
        _p("abdomen.upper", "上腹（胃）"), _p("abdomen.navel", "肚脐周围"), _p("abdomen.lower", "下腹"),
        _p("abdomen.l", "左腹"), _p("abdomen.r", "右腹"),
    ], side="front"),
    _p("shoulder", "肩膀", [_p("shoulder.l", "左肩"), _p("shoulder.r", "右肩")]),
    _p("back", "背部", [_p("back.upper", "上背"), _p("back.mid", "中背"), _p("back.scapula", "肩胛骨")], side="back"),
    _p("waist", "腰", [_p("waist.center", "腰椎"), _p("waist.l", "左腰"), _p("waist.r", "右腰")], side="back"),
    _p("arm", "手臂", [
        _p("arm.l", "左臂", [_p("arm.l.upper", "上臂"), _p("arm.l.elbow", "手肘"), _p("arm.l.fore", "前臂"), _p("arm.l.wrist", "手腕"), _p("arm.l.hand", "手掌/手指")]),
        _p("arm.r", "右臂", [_p("arm.r.upper", "上臂"), _p("arm.r.elbow", "手肘"), _p("arm.r.fore", "前臂"), _p("arm.r.wrist", "手腕"), _p("arm.r.hand", "手掌/手指")]),
    ]),
    _p("hip", "臀部", [_p("hip.l", "左臀"), _p("hip.r", "右臀"), _p("hip.tail", "尾骨")], side="back"),
    _p("knee", "膝盖", [
        _p("knee.l", "左膝", [_p("knee.l.inner", "内侧"), _p("knee.l.outer", "外侧"), _p("knee.l.patella", "髌骨"), _p("knee.l.back", "腿窝")]),
        _p("knee.r", "右膝", [_p("knee.r.inner", "内侧"), _p("knee.r.outer", "外侧"), _p("knee.r.patella", "髌骨"), _p("knee.r.back", "腿窝")]),
    ]),
    _p("leg", "腿脚", [
        _p("leg.l", "左腿", [_p("leg.l.thigh", "大腿"), _p("leg.l.calf", "小腿"), _p("leg.l.ankle", "脚踝"), _p("leg.l.foot", "脚")]),
        _p("leg.r", "右腿", [_p("leg.r.thigh", "大腿"), _p("leg.r.calf", "小腿"), _p("leg.r.ankle", "脚踝"), _p("leg.r.foot", "脚")]),
    ]),
    _p("skin", "皮肤（全身）"),
    _p("whole", "全身/说不清"),
]


def part_label(code: str) -> str | None:
    def walk(nodes, trail):
        for n in nodes:
            labels = trail + [n["label"]]
            if n["code"] == code:
                return " · ".join(labels)
            if "children" in n:
                r = walk(n["children"], labels)
                if r:
                    return r
        return None

    return walk(BODY_PARTS, [])
