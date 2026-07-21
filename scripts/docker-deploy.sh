#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 旅行 Agent / Tavily 相关：根 .env 缺失或为空时，从 backend/.env 补全
MERGE_KEYS=(
  AMAP_API_KEY
  TAVILY_API_KEY
  JUHE_TRAIN_API_KEY
  JUHE_FLIGHT_API_KEY
  HTTP_TIMEOUT_SECONDS
  TAVILY_MAX_RESULTS
)

get_env_value() {
  local file="$1"
  local key="$2"
  if [ ! -f "$file" ]; then
    return 0
  fi
  grep -E "^${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/^["'\''"]//;s/["'\''"]$//' || true
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp

  if grep -qE "^${key}=" "$file"; then
    tmp="$(mktemp)"
    while IFS= read -r line || [ -n "$line" ]; do
      if [[ "$line" =~ ^${key}= ]]; then
        printf '%s=%s\n' "$key" "$value"
      else
        printf '%s\n' "$line"
      fi
    done < "$file" > "$tmp"
    mv "$tmp" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

merge_env_from_backend() {
  local backend_env="$ROOT_DIR/backend/.env"
  local root_env="$ROOT_DIR/.env"
  local merged=0

  if [ ! -f "$backend_env" ]; then
    return 0
  fi

  for key in "${MERGE_KEYS[@]}"; do
    local root_val backend_val
    root_val="$(get_env_value "$root_env" "$key")"
    backend_val="$(get_env_value "$backend_env" "$key")"

    if [ -n "$backend_val" ] && [ -z "$root_val" ]; then
      set_env_value "$root_env" "$key" "$backend_val"
      echo "[信息] 从 backend/.env 合并 ${key}"
      merged=$((merged + 1))
    fi
  done

  if [ "$merged" -gt 0 ]; then
    echo "[信息] 共合并 ${merged} 项旅行 Agent 配置到 .env"
  fi
}

if [ ! -f ".env" ]; then
  echo "[提示] 未找到 .env，从 .env.docker.example 复制..."
  cp .env.docker.example .env
fi

merge_env_from_backend

missing=()
for required in SECRET_KEY API_KEY_ENCRYPTION_KEY; do
  if [ -z "$(get_env_value ".env" "$required")" ]; then
    missing+=("$required")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "[重要] 请编辑 .env，至少设置: ${missing[*]}"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[错误] 未安装 Docker"
  exit 1
fi

echo "[信息] 构建并启动容器..."
docker compose up -d --build

echo ""
echo "[完成] 部署已启动"
echo "  查看状态: docker compose ps"
echo "  查看日志: docker compose logs -f"

echo "  访问地址: http://localhost:8081"
