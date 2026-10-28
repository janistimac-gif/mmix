# mmix · ikone za tipke (Stream Dock in Stream Deck)

Komplet ikon za tipke, s katerimi upravljaš **mmix** (glasnost, utišanje,
master, izbira naprave, osvežitev, aplikacije). Videz sledi mmix temni temi:
kartica `#12161d`, moder obroč `#38bdf8`, zelena `#34d399`, rdeča `#fb7185`.

## Vsebina

```
streamdock/mmix.sdIconPack/     paket za SOOMFON Stream Controller (128 px)
streamdock/mmix.sdIconPack.zip  isti paket, za prenos na drug računalnik
mmix.streamDeckIconPack         paket za Elgato Stream Deck (144 px)
mmix.sdIconPack/                Elgato paket, razpakiran
icons/                          144 × 144 PNG s slovenskimi podnapisi
icons_clean/                    144 × 144 PNG brez podnapisov
preview.png                     pregled obeh kompletov
```

Vsak paket vsebuje **38 ikon**: 19 motivov (10 osnovnih + 9 kanalnih), vsak z napisom in brez njega.

| Datoteka | Napis | Pomen |
|---|---|---|
| `volume_up.png` | GLASNEJE | dvig glasnosti (master ali izbran kanal) |
| `volume_down.png` | TIŠJE | znižanje glasnosti |
| `mute.png` | UTIŠAJ | utišanje (rdeče stanje) |
| `sound.png` | ZVOK | zvok vklopljen (zeleno stanje) |
| master.png | MASTER | vsi izhodni kanali |
| ch_speakers_+.png | ZVOČNIKI + | glasneje za izhodne zvočnike |
| ch_speakers_-.png | ZVOČNIKI − | tišje za izhodne zvočnike |
| ch_speakers_x.png | ZVOČNIKI × | utišaj za izhodne zvočnike |
| ch_headphones_+.png | SLUŠALKE + | glasneje za slušalke |
| ch_headphones_-.png | SLUŠALKE − | tišje za slušalke |
| ch_headphones_x.png | SLUŠALKE × | utišaj za slušalke |
| ch_monitor_+.png | ZASLON + | glasneje za HDMI/monitor |
| ch_monitor_-.png | ZASLON − | tišje za HDMI/monitor |
| ch_monitor_x.png | ZASLON × | utišaj za HDMI/monitor |
| `device.png` | NAPRAVA | preklop izhodne naprave |
| `r`refresh.png`` | OSVEŽI | ponovno branje naprav |
| `apps.png` | APLIKACIJE | plošča aplikacij / usmerjanje |
| `open.png` | MMIX | zagon ali fokus mmix |
| `blank.png` | – | prazna kartica za lastno ikono/napis |

---

## SOOMFON Stream Controller (program Stream Dock)

SOOMFON uporablja program **Stream Controller / Stream Dock** (Mirabox), ki
**ne** zna uvoziti Elgatovih `.streamDeckIconPack`. Pravi format je mapa
`*.sdIconPack` z ikonami 128 × 128 px in manifestom, ki vsebuje
`"Images": "icons"`.

### 1. Vtičnik mmix (priporočeno)

mmix se v Stream Controllerju prikaže kot **lastna kategorija `mmix`** v zavihku
**Keys**, tako kot Discord ali OBS – ničesar ni treba ročno povezovati z
bližnjicami. V kategoriji je **14 dejanj**, vsako ima svojo ikono:

| Skupina | Dejanja |
|---|---|
| MASTER | Glasneje · Tišje · Utišaj |
| ZVOČNIKI | Glasneje · Tišje · Utišaj |
| SLUŠALKE | Glasneje · Tišje · Utišaj |
| ZASLON | Glasneje · Tišje · Utišaj |
| mmix | Prikaži mmix · Osveži naprave |

Dejanja povleci na tipke – ikona je del dejanja, zato je ni treba izbirati
posebej.

**Pogoj:** mmix mora teči (lahko minimiziran). Vtičnik se z njim pogovarja po
lokalnem mostu `http://127.0.0.1:28197`, ki ga mmix odpre sam. Če mmix ni
zagnan, tipke ne naredijo nič.

**Namestitev oziroma posodobitev:**

```powershell
python fix_mm_plugin.py          # manifest + stran vtičnika
python make_mmix_plugin_keys.py  # ikone dejanj
```

Nato Stream Controller **popolnoma zapri** (ikona v sistemski vrstici →
*Exit*) in ga znova zaženi. Vtičnik se naloži ob zagonu; v dnevniku
`%APPDATA%\HotSpot\StreamDock\logs\log-*.txt` se pojavi vrstica
`Plugin ... com.jbj.mmix.sdPlugin is now connected`.

> Če kategorije `mmix` ni na seznamu, preveri, da mapa
> `%APPDATA%\HotSpot\StreamDock\plugins\com.jbj.mmix.sdPlugin` vsebuje
> `manifest.json`, `plugin\index.html` in vse PNG v `icon\`. Manjkajoča ikona
> prepreči nalaganje vtičnika.

**Katero napravo upravlja ZVOČNIKI / SLUŠALKE / ZASLON?**
Ob prvem pritisku mmix izbere napravo iste vrste, ki ima najvišjo glasnost
(torej tisto, ki je dejansko v uporabi), in si jo zapomni v
`%APPDATA%\VolumeMixer\hotkeys.json` pod `bridge_targets`. Če želiš drugo
napravo, tam zamenjaj vrednost z ID-jem naprave – ali pa uporabi kanalske
bližnjice v mmixu (**Bližnjice → Kanali**), kjer kanal izbereš neposredno.

### 2. Namestitev celotne knjižnice ikon

Na tem računalniku je program nameščen v
`C:\Program Files (x86)\Stream Controller`, mapa za ikone pa je
`C:\Program Files (x86)\Stream Controller\icons`.

1. Zapri **Stream Controller** (ikona v sistemski vrstici → *Exit*).
2. Kopiraj mapo **`streamdeck\streamdock\mmix.sdIconPack`** v mapo
   `C:\Program Files (x86)\Stream Controller\icons`.
   Za pisanje v `Program Files` so potrebne skrbniške pravice.
3. **Pomembno:** če mapa `mmix.sdIconPack` obstaja še v
   `%APPDATA%\HotSpot\StreamDock\icons`, jo izbriši. Aplikacija bere obe
   mapi, zato bi se paket sicer prikazal dvakrat.
4. Znova zaženi Stream Controller.
5. Izberi tipko → klikni sličico ikone → **Open the Icon Library**
   (*Odpri knjižnico ikon*) → izberi paket **mmix**.

> Vmesnik Stream Controllerja je v angleščini (slovenskega prevoda program nima), zato so v nadaljevanju navedena angleška imena menijev.
>
> **Iskanje ikon:** knjižnica ikon filtrira po imenih ikon, ne po imenu paketa. Iskalnik bo našel kanalske ikone po imenu naprave (npr. zvočniki, slušalke, zaslon) in dejanju (+, -, utišaj). V knjižnici se prikaže mmix (38).

Namesto ročnega kopiranja lahko poženeš priloženo skripto (sama zahteva
skrbniške pravice):

```powershell
powershell -ExecutionPolicy Bypass -File streamdeck\install_streamdock.ps1
```

### 3. Posamezna ikona na tipko (brez namestitve paketa)

Ta način deluje vedno, tudi če se paket ne prikaže v knjižnici:

1. V Stream Controllerju izberi tipko.
2. Z desno tipko klikni **predogled ikone** → **Select Local File**
   (*Izberi lokalno datoteko*).
3. Izberi PNG iz `streamdeck\icons\` (z napisom) ali
   `streamdeck\icons_clean\` (brez napisa).

Ikono lahko tudi povlečeš neposredno na predogled. Podprti so PNG, JPG, BMP
in GIF.

> Če se paket po ponovnem zagonu ne prikaže, preveri, da je mapa res v
> `...\Stream Controller\icons` in da se ime konča na `.sdIconPack`.

---

## Elgato Stream Deck

1. Dvoklikni **`mmix.streamDeckIconPack`** – Stream Deck doda ikone v svojo
   knjižnico.
2. Na tipki odpri spodnjo puščico → **Open Stream Deck Icon Library** →
   izberi **mmix**.

Če dvoklik ne deluje (starejša različica): zapri Stream Deck, kopiraj mapo
**`mmix.sdIconPack`** v `%APPDATA%\Elgato\StreamDeck\IconPacks` in ga znova
zaženi.

---

## Uporaba

**Stream Controller:** najlažje z vtičnikom – v zavihku **Keys** izberi
kategorijo **mmix** in povleci dejanje na tipko (glej razdelek 1 zgoraj).

**Stream Deck (Elgato) in starejši način:** ikono iz knjižnice (ali iz
`icons/`) nastavi na tipko in nanjo dodaj akcijo **Hotkey** s kombinacijo, ki jo
mmix uporablja (spodnja tabela). Za toggle mute uporabi `sound.png` in
`mute.png` kot dve stanji iste tipke.

`icons_clean/` uporabi, kadar želiš napis dodati prek polja *Title*.

## Privzete bližnjice

mmix ima vgrajene **globalne bližnjice**, zato na Elgato Stream Decku plugin ni
potreben – dovolj je akcija *Hotkey*.

| Ikona | Akcija | Privzeta kombinacija |
|---|---|---|
| `volume_up.png` | Hotkey | `Ctrl+Alt+Shift+Up` |
| `volume_down.png` | Hotkey | `Ctrl+Alt+Shift+Down` |
| `mute.png` / `sound.png` | Hotkey | `Ctrl+Alt+Shift+M` |
| `r`refresh.png`` | Hotkey | `Ctrl+Alt+Shift+R` |
| `open.png` | Hotkey | `Ctrl+Alt+Shift+O` |
| `master.png`, `device.png`, `apps.png`, `blank.png` | – | za zdaj brez akcije |

Glasnost in utišanje delujeta privzeto na **MASTER** (vse izhodne naprave) po
5 % na pritisk. Ob spremembi se prikaže OSD. `open.png` prikaže mmix v ospredje,
`r`refresh.png`` ponovno prebere naprave.

**Kanalne bližnjice (per-channel):** v mmix odpri **Bližnjice** → zavihek
**Kanali**. Za vsak prikazan kanal (MASTER in izhodne naprave, npr. zvočniki,
slušalke, zaslon) lahko dodeliš svojo kombinacijo tipk za **glasneje / tišje /
utišaj**. Izbrane kombinacije delujejo globalno tudi, ko je mmix v
ozadju/minimiziran. Za vsako dejanje uporabi ustrezno kanalsko ikono iz paketa
mmix (npr. ZVOČNIKI +, SLUŠALKE ×). OSD prikaže ime kanala, ki ga upravljaš.

> **Če se kombinacija ne sproži:** odpri mmix → **Bližnjice** in preveri, ali je
> kombinacijo morda zasedla druga aplikacija. Tam jo lahko spremeniš; nato v
> Stream Controllerju vpiši novo. `master.png`, `device.png` in `apps.png` so
> za zdaj samo oznake (mmix zanje še nima globalnih dejanj).

## Ponovno generiranje

```powershell
python make_streamdeck_icons.py
```

Skripta nariše ikone 4× povečano in jih pomanjša z LANCZOS (enako kot gumbi v
`mmix.py`). Hkrati zgradi oba paketa: `streamdock/mmix.sdIconPack` (128 × 128,
Stream Dock) in `mmix.streamDeckIconPack` (144 × 144, Elgato). Barve in oblike
so v `make_streamdeck_icons.py`.
