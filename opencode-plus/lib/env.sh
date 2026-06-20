# Shared env loading for OpenCode+ llama scripts.
# Resolves ${HOME}/~/ when running as root or via sudo.

_ll_effective_home() {
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

_ll_expand_path() {
    local v="$1"
    local eh="${EFFECTIVE_HOME:-$(_ll_effective_home)}"
    case "$v" in
        '${HOME}'*) printf '%s' "${eh}${v#\$\{HOME\}}" ;;
        '$HOME'*)   printf '%s' "${eh}${v#\$HOME}" ;;
        '~/'*)      printf '%s' "${eh}/${v#\~/}" ;;
        *)          printf '%s' "$v" ;;
    esac
}

# True if llama-server --help advertises draft-mtp (avoids pipefail/SIGPIPE from grep -q).
llama_help_has_draft_mtp() {
    local bin="${1:?llama-server path required}"
    local help
    help="$("$bin" --help 2>&1 || true)"
    grep -Fq 'draft-mtp' <<<"$help"
}

# Usage: load_llama_env /path/to/project/root key1 key2 ...
load_llama_env() {
    local project_root="$1"
    shift
    local -a keys=("$@")
    local env_path key value wanted

    EFFECTIVE_HOME="$(_ll_effective_home)"
    export EFFECTIVE_HOME

    for env_path in \
        "$project_root/.env" \
        "$project_root/.env.llamacpp" \
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
                    export "$key=$(_ll_expand_path "$value")"
                    break
                fi
            done
        done < "$env_path"
    done
}
