#!/usr/bin/env bash
set -euxo pipefail

exec > >(tee -a /var/log/markdash-bootstrap.log) 2>&1

REPO_URL="${repo_url}"
GIT_REF="${git_ref}"
APP_DIR=/opt/app

# -- packages --
dnf install -y docker git

# -- docker engine --
systemctl enable --now docker
usermod -aG docker ec2-user

# -- docker compose v2 plugin --
mkdir -p /usr/local/lib/docker/cli-plugins
COMPOSE_VERSION="v2.29.7"
COMPOSE_URL="https://github.com/docker/compose/releases/download/$${COMPOSE_VERSION}/docker-compose-linux-x86_64"
curl -fsSL "$${COMPOSE_URL}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# -- source checkout (idempotent on re-run) --
if [ -d "$${APP_DIR}/.git" ]; then
  git -C "$${APP_DIR}" fetch --all --tags --prune
  git -C "$${APP_DIR}" checkout "$${GIT_REF}"
  git -C "$${APP_DIR}" pull --ff-only || true
else
  rm -rf "$${APP_DIR}"
  git clone "$${REPO_URL}" "$${APP_DIR}"
  git -C "$${APP_DIR}" checkout "$${GIT_REF}"
fi

# -- env file --
cat > "$${APP_DIR}/.env" <<EOF
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/markdash
POLYMARKET_BASE_URL=${polymarket_base_url}
ANTHROPIC_API_KEY=${anthropic_api_key}
EOF
chmod 600 "$${APP_DIR}/.env"

# -- build + run stack --
cd "$${APP_DIR}"
docker compose pull --ignore-buildable || true
docker compose up -d --build --remove-orphans

echo "markdash bootstrap complete"
