#!/bin/bash

set -euo pipefail

# NOTE(robinson,crag) - Can remove the ssh private key mount when unstructured repo is public
SSH_PRIVATE_KEY=${SSH_PRIVATE_KEY:-""}

if [ -z "$SSH_PRIVATE_KEY" ]; then
  if [ -r "$HOME"/.ssh/id_rsa ]; then
      SSH_PRIVATE_KEY="$HOME"/.ssh/id_rsa
  elif [ -r "$HOME"/.ssh/id_ed25519 ]; then
      SSH_PRIVATE_KEY="$HOME"/.ssh/id_ed25519
  fi

  if [ -z "$SSH_PRIVATE_KEY" ]; then
    echo no private ssh key found at ~/.ssh/id_ed25519 or ~/.ssh/id_rsa
    echo set env var SSH_PRIVATE_KEY with the location and try again
    exit 1
  fi
elif ! [ -r "$SSH_PRIVATE_KEY" ]; then
  echo SSH_PRIVATE_KEY set to non-existent location. fix and try again
  exit 1
fi


DOCKER_BUILDKIT=1 docker buildx build --platform=linux/amd64 -f docker/Dockerfile${BUILD_TYPE} \
  --build-arg PIP_VERSION="$PIP_VERSION" \
  --progress plain \
  --secret id=ssh_key,src="$SSH_PRIVATE_KEY" \
  -t pipeline-family-"$PIPELINE_FAMILY"-dev${BUILD_TYPE}:latest .
