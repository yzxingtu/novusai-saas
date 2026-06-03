#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LOG_FILE=${SCRIPT_DIR}/build-local-docker-image.log
ERROR=""
IMAGE_NAME=${IMAGE_NAME:-novusai-web-antd-local}
CONTAINER_NAME=${CONTAINER_NAME:-novusai-web-antd-local}
VITE_APP_TITLE=${VITE_APP_TITLE:-NovusAI SaaS}
VITE_APP_NAMESPACE=${VITE_APP_NAMESPACE:-novusai-web-saas}

function require_build_arg() {
    local name="$1"
    local value="${!name:-}"
    if [[ -z "${value}" ]]; then
        ERROR="${name} must be set for a production frontend image"
    fi
}

function require_https_url() {
    local name="$1"
    local value="${!name:-}"
    if [[ -n "${value}" && "${value}" != https://* ]]; then
        ERROR="${name} must start with https:// for a production frontend image"
    fi
}

function reject_public_placeholder() {
    local name="$1"
    local value="${!name:-}"
    local lower
    lower=$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')
    case "${lower}" in
        *example.invalid*|*example.com*|*localhost*|*127.0.0.1*|*0.0.0.0*|*.local*|http://*|*change-me*|*please-replace*|*replace-me*)
            ERROR="${name} must be a real production value"
            ;;
    esac
}

function validate_build_args() {
    require_build_arg "VITE_GLOB_API_URL"
    require_build_arg "VITE_PLATFORM_DOMAINS"
    require_build_arg "VITE_APP_STORE_SECURE_KEY"
    require_https_url "VITE_GLOB_API_URL"
    reject_public_placeholder "VITE_GLOB_API_URL"
    reject_public_placeholder "VITE_PLATFORM_DOMAINS"
    reject_public_placeholder "VITE_APP_STORE_SECURE_KEY"
}

function stop_and_remove_container() {
    docker stop "${CONTAINER_NAME}" >/dev/null 2>&1
    docker rm "${CONTAINER_NAME}" >/dev/null 2>&1
}

function remove_image() {
    docker rmi "${IMAGE_NAME}" >/dev/null 2>&1
}

function install_dependencies() {
    cd "${SCRIPT_DIR}/../.."
    pnpm install || ERROR="install_dependencies failed"
}

function build_image() {
    docker build "${SCRIPT_DIR}/../../.." \
      -f "${SCRIPT_DIR}/Dockerfile" \
      -t "${IMAGE_NAME}" \
      --build-arg "VITE_GLOB_API_URL=${VITE_GLOB_API_URL}" \
      --build-arg "VITE_PLATFORM_DOMAINS=${VITE_PLATFORM_DOMAINS}" \
      --build-arg "VITE_APP_TITLE=${VITE_APP_TITLE}" \
      --build-arg "VITE_APP_NAMESPACE=${VITE_APP_NAMESPACE}" \
      --build-arg "VITE_APP_STORE_SECURE_KEY=${VITE_APP_STORE_SECURE_KEY}" \
      || ERROR="build_image failed"
}

function log_message() {
    if [[ ${ERROR} != "" ]];
    then
        >&2 echo "build failed, Please check build-local-docker-image.log for more details"
        >&2 echo "ERROR: ${ERROR}"
        exit 1
    else
        echo "docker image with tag '${IMAGE_NAME}' built successfully. Use below sample command to run the container"
        echo ""
        echo "docker run -d -p 8010:8080 --name ${CONTAINER_NAME} ${IMAGE_NAME}"
        echo ""
        echo "Required build args came from VITE_GLOB_API_URL, VITE_PLATFORM_DOMAINS, VITE_APP_TITLE, VITE_APP_NAMESPACE, and VITE_APP_STORE_SECURE_KEY."
    fi
}

echo "Info: Stopping and removing existing container and image" | tee ${LOG_FILE}
stop_and_remove_container
remove_image

validate_build_args

if [[ ${ERROR} == "" ]]; then
    echo "Info: Installing dependencies" | tee -a ${LOG_FILE}
    install_dependencies 1>> ${LOG_FILE} 2>> ${LOG_FILE}
fi

if [[ ${ERROR} == "" ]]; then
    echo "Info: Building docker image" | tee -a ${LOG_FILE}
    build_image 1>> ${LOG_FILE} 2>> ${LOG_FILE}
fi

log_message | tee -a ${LOG_FILE}
