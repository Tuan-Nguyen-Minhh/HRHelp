#!/usr/bin/env bash
set -euo pipefail

# Local ECS deploy path that does not use GitHub Actions.
# It builds the backend image locally, pushes it to ECR, then asks ECS to
# replace the running task so it pulls the new image.

AWS_REGION="${AWS_REGION:-ap-south-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-817896957194}"
ECR_REPOSITORY="${ECR_REPOSITORY:-p029-ai20k-api}"
ECS_CLUSTER="${ECS_CLUSTER:-p029-ai20k-cluster}"
ECS_SERVICE="${ECS_SERVICE:-p029-ai20k-service}"
PLATFORM="${PLATFORM:-linux/amd64}"

if command -v git >/dev/null 2>&1 && git rev-parse --short HEAD >/dev/null 2>&1; then
  IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
else
  IMAGE_TAG="${IMAGE_TAG:-local}"
fi

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"
LATEST_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command aws
require_command docker

echo "Checking AWS identity..."
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null

echo "Checking ECR repository: ${ECR_REPOSITORY}"
aws ecr describe-repositories \
  --repository-names "$ECR_REPOSITORY" \
  --region "$AWS_REGION" >/dev/null

echo "Logging in to ECR: ${ECR_REGISTRY}"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "Building and pushing ${IMAGE_URI}"
docker buildx build \
  --platform "$PLATFORM" \
  --tag "$IMAGE_URI" \
  --tag "$LATEST_URI" \
  --push \
  .

echo "Forcing ECS service deployment: ${ECS_CLUSTER}/${ECS_SERVICE}"
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$ECS_SERVICE" \
  --force-new-deployment \
  --region "$AWS_REGION" >/dev/null

echo "Waiting for service stability..."
aws ecs wait services-stable \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --region "$AWS_REGION"

echo "Deployed ${IMAGE_URI}"
