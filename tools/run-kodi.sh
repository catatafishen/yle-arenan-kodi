#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
addon_root="$HOME/.var/app/tv.kodi.Kodi/data/addons"
addon_dir="$addon_root/plugin.video.ylearenakodi"
legacy_addon_dir="$HOME/.var/app/tv.kodi.Kodi/data/kodi/addons/plugin.video.ylearenakodi"
profile_dir="$HOME/.var/app/tv.kodi.Kodi/data/userdata"
settings_file="$profile_dir/guisettings.xml"

mkdir -p "$addon_root"
if [ -L "$legacy_addon_dir" ] && [ "$(readlink -f "$legacy_addon_dir")" = "$project_dir" ]; then
  rm "$legacy_addon_dir"
fi
if [ -L "$addon_dir" ]; then
  rm "$addon_dir"
elif [ -d "$addon_dir" ] && [ -f "$addon_dir/.yle-arenakodi-development-copy" ]; then
  rm -rf "$addon_dir"
elif [ -e "$addon_dir" ]; then
  printf 'Refusing to replace existing non-development add-on: %s\n' "$addon_dir" >&2
  exit 1
fi
mkdir "$addon_dir"
cp "$project_dir/addon.xml" "$project_dir/default.py" "$addon_dir/"
cp -a "$project_dir/yleareena" "$project_dir/resources" "$addon_dir/"
touch "$addon_dir/.yle-arenakodi-development-copy"

if [ -f "$settings_file" ]; then
  SETTINGS_FILE="$settings_file" python3 - <<'PY'
import os
import tempfile
import xml.etree.ElementTree as ET

path = os.environ["SETTINGS_FILE"]
tree = ET.parse(path)
root = tree.getroot()
values = {
    "videoscreen.screenmode": "WINDOW",
    "videoscreen.fakefullscreen": "false",
}
for setting in root.findall("setting"):
    setting_id = setting.get("id")
    if setting_id in values:
        setting.text = values[setting_id]
        setting.attrib.pop("default", None)
fd, temporary = tempfile.mkstemp(prefix="guisettings.", suffix=".xml", dir=os.path.dirname(path))
os.close(fd)
try:
    tree.write(temporary, encoding="UTF-8", xml_declaration=False)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
fi

exec flatpak run tv.kodi.Kodi --windowing=x11
