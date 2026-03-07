#!/bin/sh
set -eu

BOOT_ID="$(cat /proc/sys/kernel/random/boot_id)"
sed "s/__PROMTAIL_BOOT_ID__/${BOOT_ID}/" /etc/promtail/config.yml > /tmp/promtail-config.yml

exec promtail -config.file=/tmp/promtail-config.yml
