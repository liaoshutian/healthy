#!/bin/sh
# 每日在本机备份数据库和图片。加到 crontab：
#   30 3 * * * cd /opt/healthy/deploy && mkdir -p backups && ./backup.sh >> backups/backup.log 2>&1
# 备份都留在 Lighthouse 本机的 deploy/backups/，建议定期再拷一份到别的地方（比如自己电脑），
# 或者在腾讯云控制台给这台 Lighthouse 开自动快照。
set -e
cd "$(dirname "$0")"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M)
docker compose exec -T db pg_dump -U qingning qingning | gzip > "backups/db-$STAMP.sql.gz"
tar -czf "backups/uploads-$STAMP.tar.gz" -C data uploads
# 数据库留 14 天，图片包较大只留 3 天（图片本身一直在 data/uploads 里）
find backups -name 'db-*.sql.gz' -mtime +14 -delete
find backups -name 'uploads-*.tar.gz' -mtime +3 -delete
echo "$(date) backup ok: $STAMP"
