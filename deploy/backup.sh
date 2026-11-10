#!/bin/sh
# 每日数据库备份并上传 COS。加到 crontab：
#   30 3 * * * cd /opt/healthy/deploy && ./backup.sh >> backups/backup.log 2>&1
# 上传需要安装 coscli 并配置好（https://cloud.tencent.com/document/product/436/63143）。
set -e
cd "$(dirname "$0")"
mkdir -p backups
FILE="qingning-$(date +%Y%m%d-%H%M).sql.gz"
docker compose exec -T db pg_dump -U qingning qingning | gzip > "backups/$FILE"
if command -v coscli >/dev/null 2>&1; then
  coscli cp "backups/$FILE" "cos://${COS_BACKUP_BUCKET:-qingning-backup}/db/$FILE"
fi
# 本地只留 14 天
find backups -name 'qingning-*.sql.gz' -mtime +14 -delete
echo "$(date) backup ok: $FILE"
