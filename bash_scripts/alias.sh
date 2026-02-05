alias claudette='SKIP_SERENA=true claude'
cc() {
  clear
  (
    if [ -f .local.env ]; then
      set -a
      source .local.env
      set +a
    else
      echo "No .local.env file found"
    fi
    claude "$@"
  )
}
