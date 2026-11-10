# 青柠生活

“拍一下就记好”的个人健康记录微信小程序：饮食、体成分、规律生活、身体不适四条线，用一片青柠串起每一天。
方案文档见项目内的《交互与产品方案 v0.1》。

```
backend/       Python FastAPI 后端（PostgreSQL + Redis，图片存腾讯云 COS）
miniprogram/   原生微信小程序（TypeScript）
deploy/        腾讯云 Lighthouse 上的 Docker Compose、Nginx、备份脚本
```

## 第一期做了什么

| 模块 | 小程序 | 后端 |
| --- | --- | --- |
| 登录 | 静默登录，新手引导 4 屏（可跳过） | `wx.login` 换 openid，发 JWT；新用户送 7 天 Pro |
| 今日 | 一片青柠 6 瓣（早/午/晚餐、喝水、称一称、照顾自己），今日饭量用碗饭/鸡翅/盘菜/苹果展示，规律提醒，身体快照，“今天好些了吗？” | `/api/today` |
| 拍食物 | 拍照 → 结果卡（照片上标点、份量 ± 半份、改名、补一项）→ 保存；一句话记饭；和之前一样 | 大模型只“看懂”，热量由食物库算；ChatGPT 失败自动切通义千问 VL；都失败退到食物库搜索 |
| 挑战卡 | 均衡、低碳、生酮、原始人、地中海 5 张卡，可试玩 3 天、暂停、换卡 | 宏量 50 + 禁忌 30 + 推荐 20 打分，70 分点亮，一天点亮 2 顿算达成；不出现“超标/失败” |
| 体成分 | 拍 InBody 报告 / 只记体重 / 手动填写；低置信度字段标黄；偏低/标准/偏高色条；AI 解读（Pro） | 生理关系交叉校验（BMI、体脂量 + 去脂体重 ≈ 体重…），校验不过也会切换模型 |
| 规律生活 | 10 个模板 + 自定义，环形倒计时，完成/推迟 3 天，照片和花费，实际平均周期建议，写进手机日历 | 一次性订阅消息攒提醒次数，worker 每小时发提醒 |
| 不适与用药 | 正/背面人体图 → 局部 → 更细位置（三级），“上次也是这里”，症状标签和程度，每日跟进曲线，拍药盒读药名，就诊病历多图，生成病情摘要图片 | 单独授权；只记录不诊断 |
| 数据 | 月历（饭/身体/规律/生病标记）+ 某天明细；趋势（体重、体脂率、骨骼肌、内脏脂肪、每日热量，7 日平均线） | Free 只看最近 90 天 |
| 会员 | 权益对比表、识别次数、输入兑换码（**不出现价格和购买入口**） | 兑换码幂等核销、同档顺延、低档升高档按价格比折算；Redis 计配额 |
| 管理后台 | — | `/admin` 网页：批量生成兑换码、按会员 ID 开通/延期/撤销、7 天内到期名单导出、核销记录 |
| 我的 | 徽章墙、导出数据（Pro，CSV）、隐私说明、注销账号 | — |

## 本地开发

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload        # 默认 SQLite + 内存计数，打开 http://localhost:8000/api/docs
pytest -q                            # 24 个测试；设 TEST_DATABASE_URL 可跑在 PostgreSQL 上
```

开发环境没有 `WX_SECRET` 时，登录会用 code 生成假 openid，方便在开发者工具里直接调。

小程序：用微信开发者工具打开 `miniprogram/` 目录（AppID 已填），勾选“不校验合法域名”即可连 `localhost:8000`。
类型检查：`cd miniprogram && npm install && npm run typecheck`。

## 部署到 Lighthouse

```bash
git clone https://github.com/liaoshutian/healthy /opt/healthy
cd /opt/healthy/deploy
cp .env.example .env    # 填密码、AppSecret、COS、各家模型 key
mkdir certs             # 放 api.rexliao.cn 的 Nginx 证书（腾讯云免费 SSL 证书即可）
docker compose up -d --build
crontab -e              # 加一行：30 3 * * * cd /opt/healthy/deploy && ./backup.sh >> backups/backup.log 2>&1
```

API 容器启动时会自动跑数据库迁移，并把首发食物库（94 条）灌进去。

## 上线前需要 Rex 准备的

1. **域名**：`api.rexliao.cn` 解析到 Lighthouse，并确认 `rexliao.cn` 的 ICP 备案已完成。
2. **小程序后台 → 开发管理 → 服务器域名**：request、uploadFile、downloadFile 合法域名都填 `https://api.rexliao.cn`。
3. **小程序后台 → 设置 → 用户隐私保护指引**：声明相机、相册、头像、日历；不填的话这些接口调不了。
4. **订阅消息模板**：选“事项提醒”和“用药提醒”类模板，把 ID 填进 `deploy/.env` 的 `WX_TMPL_*` 和 `miniprogram/utils/config.ts`；字段名如与 `backend/app/worker.py` 里的不同需要对一下。
5. **AppSecret、COS 存储桶（私有读）、OpenAI / 通义千问 / DeepSeek 的 key**。
6. **OpenAI 的网络**：国内服务器直连 `api.openai.com` 通常不通，需要在 `OPENAI_BASE_URL` 填一个可用的转发地址；转不通时会自动用通义千问 VL 兜底。
7. 食物库份量换算和挑战卡参数是初稿，建议找营养师审一遍（`backend/app/data/foods.py`、`backend/app/services/plans.py`）。
