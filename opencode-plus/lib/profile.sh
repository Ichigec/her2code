# Load saved profile(s) from opencode+/configs/profiles/

load_opencode_plus_profile() {
    local profile="${1:?profile name required}"
    local base="${OPENCODE_PLUS_DIR:-}/configs/profiles"
    local f="$base/${profile}.env"
    [ -f "$f" ] || { echo "✗ Profile not found: $f" >&2; return 1; }
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|\#*) continue ;;
        esac
        local key="${line%%=*}"
        local value="${line#*=}"
        key="${key%$'\r'}"
        value="${value%$'\r'}"
        case "$value" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        if declare -f _ll_expand_path >/dev/null 2>&1; then
            value="$(_ll_expand_path "$value")"
        elif declare -f _oc_expand_path >/dev/null 2>&1; then
            value="$(_oc_expand_path "$value")"
        fi
        export "$key=$value"
    done <"$f"
}
