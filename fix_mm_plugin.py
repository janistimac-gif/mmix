#!/usr/bin/env python3
"""Build the mmix Stream Controller plugin (manifest + helper files).

Writes to %APPDATA%\\HotSpot\\StreamDock\\plugins\\com.jbj.mmix.sdPlugin

Notes
-----
* All stock plugins in this app store their manifest as plain UTF-8.
* ``Software.MinimumVersion`` must be LOWER than the installed app version,
  otherwise the plugin is silently skipped. Installed app is 3.10.199.0728,
  so we ask for 3.10.0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PLUGIN_DIR = (
    Path(os.environ["APPDATA"])
    / "HotSpot"
    / "StreamDock"
    / "plugins"
    / "com.jbj.mmix.sdPlugin"
)
ICON_DIR = PLUGIN_DIR / "icon"

PLUGIN_UUID = "com.jbj.mmix.sdPlugin"
APP_MIN_VERSION = "3.10.0"   # installed app reports 3.10.199.0728

# (icon slug, action uuid suffix, display name, tooltip)
# IMPORTANT: the suffix must be a SINGLE segment (no extra dots). Every plugin
# that loads in this app uses exactly one dot: "<plugin uuid>.<action>".
ACTIONS: list[tuple[str, str, str, str]] = [
    ("master_up",     "masterUp",     "Glasneje (MASTER)",        "Poveča glasnost vseh izhodov"),
    ("master_down",   "masterDown",   "Tišje (MASTER)",           "Zmanjša glasnost vseh izhodov"),
    ("master_mute",   "masterMute",   "Utišaj (MASTER)",          "Preklopi utišanje vseh izhodov"),

    ("speakers_up",   "speakersUp",   "Glasneje (ZVOČNIKI)",      "Poveča glasnost zvočnikov"),
    ("speakers_down", "speakersDown", "Tišje (ZVOČNIKI)",         "Zmanjša glasnost zvočnikov"),
    ("speakers_mute", "speakersMute", "Utišaj (ZVOČNIKI)",        "Preklopi utišanje zvočnikov"),

    ("headphones_up",   "headphonesUp",   "Glasneje (SLUŠALKE)",  "Poveča glasnost slušalk"),
    ("headphones_down", "headphonesDown", "Tišje (SLUŠALKE)",     "Zmanjša glasnost slušalk"),
    ("headphones_mute", "headphonesMute", "Utišaj (SLUŠALKE)",    "Preklopi utišanje slušalk"),

    ("monitor_up",   "monitorUp",   "Glasneje (ZASLON)",          "Poveča glasnost zaslona/HDMI"),
    ("monitor_down", "monitorDown", "Tišje (ZASLON)",             "Zmanjša glasnost zaslona/HDMI"),
    ("monitor_mute", "monitorMute", "Utišaj (ZASLON)",            "Preklopi utišanje zaslona/HDMI"),

    ("open",    "show",    "Prikaži mmix",    "Odpri okno mmix"),
    ("refresh", "refresh", "Osveži naprave",  "Ponovno naloži seznam naprav"),
]


def build_manifest() -> dict:
    actions = []
    for slug, suffix, name, tooltip in ACTIONS:
        image = f"icon/{slug}"
        actions.append(
            {
                "UUID": f"{PLUGIN_UUID}.{suffix}",
                "Name": name,
                "Tooltip": tooltip,
                "Icon": image,
                "States": [
                    {
                        "Image": image,
                        "TitleAlignment": "bottom",
                        "FontSize": "9",
                    }
                ],
                "Controllers": ["Keypad"],
                "UserTitleEnabled": False,
                "SupportedInMultiActions": True,
            }
        )
    return {
        "SDKVersion": 1,
        "Name": "mmix",
        "Author": "JBJ",
        "Version": "1.5.0",
        "Description": "Nadzor glasnosti mmix neposredno iz Stream Controllerja.",
        "Category": "mmix",
        "CategoryIcon": "icon/category",
        "Icon": "icon/plugin",
        "URL": "https://github.com/",
        "CodePath": "plugin/index.html",
        "OS": [
            {"Platform": "windows", "MinimumVersion": "10"},
            {"Platform": "mac", "MinimumVersion": "10.15"},
        ],
        "Software": {"MinimumVersion": APP_MIN_VERSION},
        "Actions": actions,
    }


PLUGIN_INDEX_HTML = """<!DOCTYPE html>
<html lang="sl">
<head>
<meta charset="utf-8">
<title>mmix</title>
<style>
  html, body { margin:0; padding:0; background:#11161f; color:#c9d4e3;
               font:12px/1.4 "Segoe UI", system-ui, sans-serif; }
  #log { padding:8px 10px; white-space:pre-wrap; opacity:.75; }
</style>
</head>
<body>
<pre id="log">mmix</pre>
<script>
/* Stream Controller / Stream Dock HTML plugin.

   The host application calls the global function
       connectElgatoStreamDeckSocket(port, uuid, registerEvent, info, actionInfo)
   after the page loads. We register over its websocket and then forward every
   key press to the local mmix helper (http://127.0.0.1:28197). */

var MMIX_KEYS = {
  "com.jbj.mmix.sdPlugin.masterUp":       ["master", "up"],
  "com.jbj.mmix.sdPlugin.masterDown":     ["master", "down"],
  "com.jbj.mmix.sdPlugin.masterMute":     ["master", "mute"],

  "com.jbj.mmix.sdPlugin.speakersUp":     ["speakers", "up"],
  "com.jbj.mmix.sdPlugin.speakersDown":   ["speakers", "down"],
  "com.jbj.mmix.sdPlugin.speakersMute":   ["speakers", "mute"],

  "com.jbj.mmix.sdPlugin.headphonesUp":   ["headphones", "up"],
  "com.jbj.mmix.sdPlugin.headphonesDown": ["headphones", "down"],
  "com.jbj.mmix.sdPlugin.headphonesMute": ["headphones", "mute"],

  "com.jbj.mmix.sdPlugin.monitorUp":      ["monitor", "up"],
  "com.jbj.mmix.sdPlugin.monitorDown":    ["monitor", "down"],
  "com.jbj.mmix.sdPlugin.monitorMute":    ["monitor", "mute"],

  "com.jbj.mmix.sdPlugin.show":           ["show", ""],
  "com.jbj.mmix.sdPlugin.refresh":        ["refresh", ""]
};

var MMIX_BRIDGE = "http://127.0.0.1:28197/action";
var websocket = null;

function mmixLog(text) {
  var el = document.getElementById("log");
  if (el) el.textContent = text;
}

/* Sproži dejanje v mmixu.

   Uporabimo "<img>" namesto fetch(): stran teče iz file://, zato bi fetch
   lahko ustavila CORS/preverjanje vsebine. Zahteva po sliki gre vedno skozi,
   vračilo pa nas ne zanima. */
function mmixFire(target, kind) {
  var url = kind
    ? MMIX_BRIDGE + "?target=" + encodeURIComponent(target) +
      "&kind=" + encodeURIComponent(kind)
    : MMIX_BRIDGE + "?name=" + encodeURIComponent(target);
  var beacon = new Image();
  beacon.src = url + "&_=" + Date.now();
  mmixLog("mmix: " + target + (kind ? " / " + kind : ""));
}

window.connectElgatoStreamDeckSocket = function (port, uuid, registerEvent) {
  try {
    if (websocket) websocket.close();
  } catch (e) {}

  websocket = new WebSocket("ws://127.0.0.1:" + port);

  websocket.onopen = function () {
    websocket.send(JSON.stringify({ event: registerEvent, uuid: uuid }));
    mmixLog("mmix pripravljen");
  };

  websocket.onerror = function () {
    mmixLog("napaka pri povezavi na Stream Controller");
  };

  websocket.onmessage = function (event) {
    var msg;
    try { msg = JSON.parse(event.data); } catch (e) { return; }
    var key = MMIX_KEYS[msg.action];
    if (!key) return;
    if (msg.event === "keyDown") {
      mmixFire(key[0], key[1]);
    }
  };
};
</script>
</body>
</html>
"""


def main() -> None:
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    (PLUGIN_DIR / "plugin").mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest()

    # plain UTF-8, like every stock plugin in this app
    (PLUGIN_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (PLUGIN_DIR / "plugin" / "index.html").write_text(
        PLUGIN_INDEX_HTML, encoding="utf-8"
    )

    # validate every referenced image actually exists
    missing = []
    refs = [manifest["Icon"], manifest["CategoryIcon"]]
    for a in manifest["Actions"]:
        refs.append(a["Icon"])
        refs.extend(s.get("Image", "") for s in a["States"])
    for ref in sorted({r for r in refs if r}):
        p = PLUGIN_DIR / f"{ref}.png"
        if not p.exists():
            missing.append(ref)

    print(f"manifest : {PLUGIN_DIR / 'manifest.json'}")
    print(f"actions  : {len(manifest['Actions'])}")
    print(f"icons    : {len(list(ICON_DIR.glob('*.png')))} PNG")
    if missing:
        print("!!! MANJKAJO IKONE:")
        for m in missing:
            print("   -", m)
    else:
        print("vse ikone so na mestu")
    print(f"software : min {APP_MIN_VERSION} (aplikacija je 3.10.199.0728)")


if __name__ == "__main__":
    main()
