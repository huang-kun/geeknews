#!/bin/bash

# 构建docker镜像脚本, 借鉴彭老师的实现, 本人也是极客时间AI Agent的二期学员
# https://github.com/DjangoPeng/GitHubSentinel/blob/main/build_image.sh

# 获取当前的 Git 分支名称
#BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# 如果需要，可以处理分支名称，例如替换无效字符
#BRANCH_NAME=${BRANCH_NAME//\//-}

# 获取当前的git tag名称（前提是得先有tag）
TAG_NAME=$(git describe --tags --exact-match HEAD)

# 使用 Git 分支或tag名称作为 Docker 镜像的标签
IMAGE_TAG="geeknews:${TAG_NAME}"

# 构建 Docker 镜像
docker build -t $IMAGE_TAG .

# 输出构建结果
echo "Docker 镜像已构建并打上标签: $IMAGE_TAG"
