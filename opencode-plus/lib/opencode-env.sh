# Shared env loading for native OpenCode+ scripts.

_oc_effective_home() {
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        getent passwd "$SUDO_USER" | cut -d: -f6
        return
    fi
    if [ "$(id -u)" = "0" ] && [ -n "${PROJECT_ROOT:-}" ]; then
        local repo_owner
        repo_owner="$(stat -c '%U' "$PROJECT_ROOT" 2>/dev/null || echo "")"
        if [ -n "$repo_owner" ] && [ "$repo_owner" != "root" ]; then
            getent passwd "$repo_owner" | cut -d: -f6
            return
        fi
    fi
    printf '%s' "${HOME:-/root}"
}

_oc_expand_path() {
    local v="$1"
    local eh="${EFFECTIVE_HOME:-$(_oc_effective_home)}"
    case "$v" in
        '${HOME}'*) printf '%s' "${eh}${v#\$\{HOME\}}" ;;
        '$HOME'*)   printf '%s' "${eh}${v#\$HOME}" ;;
        '~/'*)      printf '%s' "${eh}/${v#\~/}" ;;
        *)          printf '%s' "$v" ;;
    esac
}

# Usage: load_opencode_env /path/to/project/root
load_opencode_env() {
    local project_root="$1"
    shift
    local -a keys=("$@")
    local env_path key value wanted

    EFFECTIVE_HOME="$(_oc_effective_home)"
    export EFFECTIVE_HOME PROJECT_ROOT="${PROJECT_ROOT:-$project_root}"

    for env_path in \
        "$project_root/.env" \
        "$project_root/.env.opencode" \
        "${OPENCODE_PLUS_DIR:-}/.env"; do
        [ -f "$env_path" ] || continue
        while IFS= read -r line || [ -n "$line" ]; do
            case "$line" in
                ''|\#*) continue ;;
            esac
            key="${line%%=*}"
            value="${line#*=}"
            key="${key%$'\r'}"
            value="${value%$'\r'}"
            case "$value" in
                \"*\") value="${value#\"}"; value="${value%\"}" ;;
                \'*\') value="${value#\'}"; value="${value%\'}" ;;
            esac
            for wanted in "${keys[@]}"; do
                if [ "$key" = "$wanted" ]; then
                    export "$key=$(_oc_expand_path "$value")"
                    break
                fi
            done
        done < "$env_path"
    done
}

oc_resolve_binary() {
    local eh="${EFFECTIVE_HOME:-$(_oc_effective_home)}"
    local p found=""
    for p in \
        "${OPENCODE_BIN:-}" \
        "$eh/.local/bin/opencode" \
        "$eh/.opencode/bin/opencode" \
        /usr/local/bin/opencode; do
        if [ -n "$p" ] && [ -x "$p" ]; then
            printf '%s' "$p"
            return 0
        fi
    done
    found="$(command -v opencode 2>/dev/null || true)"
    if [ -n "$found" ] && [ -x "$found" ]; then
        printf '%s' "$found"
        return 0
    fi
    return 1
}
