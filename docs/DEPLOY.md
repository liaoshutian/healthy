# 吃饱睡好簿 · 从零到上线

整体分三块，按顺序做：

1. **后端**：部署在 Lighthouse 上，所有服务和数据都在这一台机器
2. **微信公众平台**：配置小程序后台
3. **小程序**：在开发者工具里上传、提审、发布

```
小程序 ──HTTPS──> healthy.rexliao.cn (Lighthouse: Nginx → FastAPI → PostgreSQL / Redis / 本机图片)
                                              └──> 大模型（OpenAI 走你的中转、通义千问、DeepSeek）
```

---

## 0. 开工前要准备好的东西

| 东西 | 去哪里拿 | 用在哪 |
| --- | --- | --- |
| `rexliao.cn` ICP 备案 | 腾讯云备案 | 小程序只能连备案过的 HTTPS 域名 |
| 小程序备案 | 公众平台首页 → 小程序备案 | 没备案不能发布上线 |
| AppSecret | 公众平台 → 开发管理 → 开发设置 → 生成 | `.env` 的 `WX_SECRET` |
| SSL 证书 | 腾讯云 → SSL 证书 → 免费证书，申请 `healthy.rexliao.cn`，下载 **Nginx** 版 | `deploy/certs/` |
| OpenAI 中转地址和 key | 你自己的中转 | `OPENAI_BASE_URL`、`OPENAI_API_KEY` |
| 通义千问 key | 阿里云百炼 → API-KEY | `QWEN_API_KEY` |
| DeepSeek key | platform.deepseek.com | `DEEPSEEK_API_KEY` |

三家模型至少配一家能看图的（OpenAI 中转或通义），否则拍照识别会一直退到“手动搜索”。

---

## 1. 后端：Lighthouse

### 1.1 机器准备

- 镜像选带 Docker 的（Lighthouse 有 “Docker CE” 应用镜像）；或者自己装：`curl -fsSL https://get.docker.com | sh`
- 配置建议 2 核 4G 起步，磁盘按图片量预留（每张压缩后约 200–500 KB）
- **防火墙**：Lighthouse 控制台 → 防火墙，放行 TCP 80、443（22 保留给 SSH）
- **DNS**：`healthy.rexliao.cn` 加一条 A 记录指向 Lighthouse 公网 IP

> 如果 OpenAI 中转也在这台机器上并占用了 80/443，需要把它和本项目的 Nginx 合并成一个，或给中转换个端口。

### 1.2 拉代码、填配置

```bash
git clone https://github.com/liaoshutian/healthy /opt/healthy
cd /opt/healthy/deploy
cp .env.example .env
vim .env
```

`.env` 里要动的项：

| 变量 | 填什么 |
| --- | --- |
| `POSTGRES_PASSWORD` | 长随机串，`openssl rand -hex 24` |
| `JWT_SECRET` | 长随机串，`openssl rand -hex 32`；上线后不要再改，改了所有人要重新登录 |
| `ADMIN_TOKEN` | 管理后台口令，长一点 |
| `WX_SECRET` | 小程序 AppSecret |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` | 你的中转地址（形如 `https://xxx/v1`）和 key |
| `OPENAI_VISION_MODEL` 等 | 默认 `gpt-6.1-terra`，确认中转支持；换老模型（gpt-4.1/4o）时把 `OPENAI_REASONING_EFFORT` 留空 |
| `QWEN_API_KEY`、`DEEPSEEK_API_KEY` | 各家 key |

已经填好、一般不用动的：`WX_APPID`、`WX_TMPL_ROUTINE`（订阅消息模板）、`PUBLIC_BASE_URL`、`WX_MINIPROGRAM_STATE=formal`。

> 测试阶段想让订阅消息点开进体验版，把 `WX_MINIPROGRAM_STATE` 改成 `trial`，正式发布后再改回 `formal`。

### 1.3 证书

```bash
mkdir -p certs
# 把下载的 Nginx 证书包里的两个文件放进去，文件名要和 nginx/qingning.conf 一致：
#   certs/healthy.rexliao.cn_bundle.crt
#   certs/healthy.rexliao.cn.key
```

### 1.4 启动

```bash
docker compose up -d --build
docker compose ps                 # api、worker、db、redis、nginx 都是 running
docker compose logs -f api        # 看到 Uvicorn running 即可，Ctrl+C 退出
curl https://healthy.rexliao.cn/api/ping
```

API 启动时会自动建表/迁移，并灌入首发食物库。

### 1.5 备份

```bash
crontab -e
# 加一行（每天 03:30）：
30 3 * * * cd /opt/healthy/deploy && mkdir -p backups && ./backup.sh >> backups/backup.log 2>&1
```

数据库备份留 14 天、图片包留 3 天，都在 `deploy/backups/`。建议再打开 Lighthouse 的自动快照。

### 1.6 管理后台

浏览器打开 `https://healthy.rexliao.cn/admin`，输入 `ADMIN_TOKEN`。在这里给知识星球会员批量生成兑换码、按会员 ID 开通或延期、导出快到期名单。

### 1.7 以后更新

```bash
cd /opt/healthy && git pull
cd deploy && docker compose up -d --build
```

---

## 2. 微信公众平台（mp.weixin.qq.com）

1. **基础信息**：名称“吃饱睡好簿”、头像、简介；**服务类目**选和功能相符的（个人主体选不了医疗类）。
2. **开发管理 → 开发设置 → 服务器域名**，四项都填 `https://healthy.rexliao.cn`：
   - request 合法域名
   - uploadFile 合法域名
   - downloadFile 合法域名
   - （socket 不用填）
3. **设置 → 服务内容声明 → 用户隐私保护指引**，按实际用到的勾选并写用途：
   - 选中的照片或视频、摄像头：拍食物、体测报告、药盒、病历
   - 用户头像：设置头像
   - 相册（仅写入）：保存病情摘要图片
   - 日历：把规律小事写进手机日历
   - 剪贴板：复制会员 ID（发给你开通会员用）
   
   不填的话这些接口在正式版里会直接失败。
4. **功能 → 订阅消息**：已选“日程提醒”（健康管理类目，编号 5666），ID 已写进代码，不用再动。
5. **小程序备案**：首页按引导提交，审核通过后才能发布。

---

## 3. 小程序：开发者工具

1. 安装[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)，用管理员微信扫码登录。
2. 导入项目：目录选仓库里的 `miniprogram/`，AppID 自动识别为 `wxbe81a96f3114c5f3`。
3. **本地联调**（可选）：本机跑后端后，右上角“详情 → 本地设置”勾选“不校验合法域名”，开发版会连 `http://localhost:8000`。
4. **真机预览**：点“预览”扫码。真机上的开发版也连 `localhost`，想在手机上连正式后端，用“上传”后的体验版。
5. **上传**：点“上传”，填版本号（如 `0.1.0`）和备注。
6. **体验版**：公众平台 → 版本管理 → 开发版本 → 设为体验版；成员管理里加体验成员。体验版连的是 `https://healthy.rexliao.cn`。
7. **提交审核**：版本管理 → 提交审核，填功能页面和测试账号说明（登录是静默的，不需要账号）。
8. **发布**：审核通过后在版本管理里点“发布”。

后端地址的切换逻辑在 `miniprogram/utils/config.ts`：开发版连本地，体验版和正式版连 `healthy.rexliao.cn`。

---

## 4. 上线前自查

- [ ] `curl https://healthy.rexliao.cn/api/ping` 正常
- [ ] 体验版能登录，“我的”里能看到 7 天 Pro 试用
- [ ] 拍一张食物能识别；把中转地址故意填错后会自动切到通义千问
- [ ] 拍体测报告、读药盒能出结果
- [ ] 新建一件规律小事并允许订阅，到提醒日能收到“日程提醒”
- [ ] 管理后台生成一个兑换码，在小程序“会员”页能兑换成功
- [ ] `deploy/backups/` 第二天有备份文件

## 5. 审核可能被卡的地方

- **健康/医疗相关**：个人主体不能提供诊疗服务。记录页和病情摘要上已写明“不替代医生诊断”，提审备注里也写一句“用于个人健康记录，不提供诊断和医疗建议”。
- **虚拟支付**：小程序里没有价格和购买入口，兑换码只是“激活”，备注里不要提知识星球付费。
- **AI 生成内容**：解读结果已标注“AI 生成”，审核问起时说明使用的模型服务。
