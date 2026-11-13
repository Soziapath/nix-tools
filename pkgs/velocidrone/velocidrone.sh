download_url=https://velocidrone.com/login
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/velocidrone"
install_dir="$data_dir/game"
archive_root="$data_dir/launcher.zip"

fail() {
    printf 'VelociDrone: %s\n' "$1" >&2
    if [[ ${mode:-launch} == launch && ( -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ) ]]; then
        zenity --error --title=VelociDrone --no-markup --text="$1" || true
    fi
    exit 1
}

choose_archive() {
    local answer downloads
    while true; do
        answer=
        if answer=$(zenity --question --title=VelociDrone --no-markup \
            --text=$'Sign in to your VelociDrone account and download the Linux launcher ZIP.\nThen choose the ZIP to install VelociDrone.' \
            --ok-label='Choose ZIP' --cancel-label=Cancel --extra-button='Open Download Page'); then
            break
        fi
        [[ "$answer" == 'Open Download Page' ]] || return 1
        xdg-open "$download_url" 9>&- >/dev/null 2>&1 &
    done

    downloads=$(xdg-user-dir DOWNLOAD)
    zenity --file-selection --title='Select the VelociDrone Linux ZIP' \
        --filename="${downloads%/}/" --file-filter='ZIP archives | *.zip *.ZIP'
}

install_archive() {
    local archive=$1 store_archive launcher_dir
    local -a launchers

    staging_dir=$(mktemp -d "$data_dir/.setup.XXXXXXXX") ||
        fail 'Could not create the setup directory.'
    trap 'rm -rf -- "$staging_dir"' EXIT

    cp -- "$archive" "$staging_dir/velocidrone-linux.zip" ||
        fail 'Could not read the selected ZIP.'
    if ! unzip -q "$staging_dir/velocidrone-linux.zip" -d "$staging_dir/unpacked" </dev/null; then
        fail 'Could not extract the ZIP. Choose the Linux launcher ZIP from VelociDrone.'
    fi

    mapfile -d '' -t launchers < <(find "$staging_dir/unpacked" -type f -name Launcher -print0)
    if [[ ${#launchers[@]} -ne 1 ]]; then
        fail 'The ZIP must contain one Linux Launcher.'
    fi
    launcher_dir=${launchers[0]%/*}
    if [[ ! -f "$launcher_dir/launcher.dat" || -L "$launcher_dir/launcher.dat" ]]; then
        fail 'The ZIP is missing launcher.dat next to Launcher.'
    fi
    chmod u+x -- "${launchers[0]}" || fail 'Could not make the Linux launcher executable.'

    store_archive=$(nix-store --add-fixed sha256 "$staging_dir/velocidrone-linux.zip") ||
        fail 'Could not import the ZIP into the Nix store. Check that your Nix store is available.'
    nix-store --realise --add-root "$archive_root" "$store_archive" >/dev/null ||
        fail 'Could not keep the imported ZIP in the Nix store.'
    mv -T -- "$launcher_dir" "$install_dir" || fail 'Could not save the game directory.'

    rm -rf -- "$staging_dir"
    trap - EXIT
}

case "${1:-}" in
    --use-existing | --setup-zip)
        mode=$1
        [[ $# -eq 2 ]] || fail "Usage: velocidrone $1 PATH"
        ;;
    --help)
        printf '%s\n' \
            'velocidrone [-- ARGUMENTS...]     Run the launcher, opening setup on first use.' \
            'velocidrone --setup-zip ZIP       Import the Linux ZIP and set up the launcher.' \
            'velocidrone --use-existing DIR   Register an existing VelociDrone directory.'
        exit 0
        ;;
    --)
        shift
        mode=launch
        ;;
    *)
        mode=launch
        ;;
esac

umask 077
mkdir -p -- "$data_dir" || fail 'Could not create the VelociDrone data directory.'
exec 9>"$data_dir/setup.lock"
flock 9 || fail 'Could not lock the VelociDrone data directory.'

case "$mode" in
    --use-existing)
        existing_dir=$(realpath -e -- "$2") || fail 'The game directory does not exist.'
        [[ -x "$existing_dir/Launcher" && -f "$existing_dir/launcher.dat" && -w "$existing_dir" ]] ||
            fail 'Select a writable game directory containing the executable Launcher and launcher.dat.'
        if [[ -L "$install_dir" && "$(readlink -- "$install_dir")" == "$existing_dir" ]]; then
            exit 0
        fi
        ln -sT -- "$existing_dir" "$install_dir" ||
            fail 'A VelociDrone game directory is already registered.'
        exit 0
        ;;
    --setup-zip)
        [[ ! -e "$install_dir" && ! -L "$install_dir" ]] ||
            fail 'A VelociDrone game directory is already registered.'
        install_archive "$2"
        exit 0
        ;;
esac

if [[ ! -e "$install_dir" && ! -L "$install_dir" ]]; then
    [[ -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ]] ||
        fail 'Use velocidrone --setup-zip ZIP or launch from your desktop.'
    archive=$(choose_archive) || exit 0
    install_archive "$archive"
fi

[[ -x "$install_dir/Launcher" && -f "$install_dir/launcher.dat" && -w "$install_dir" ]] ||
    fail 'The registered VelociDrone directory is missing files or is no longer writable.'
cd -P -- "$install_dir" || fail 'Could not open the VelociDrone game directory.'
exec 9>&-
exec steam-run ./Launcher "$@"
