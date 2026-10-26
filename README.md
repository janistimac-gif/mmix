# mmix

Sodoben temen mešalnik glasnosti za **vse zvočne naprave v Windows** – z master
kanalom, LED peak meterjem, preimenovanjem kanalov in kovinskimi drsniki.

![mmix](docs/screenshot.png)

> Windows 10/11 (x64) · brez nameščenega Pythona · slovenski vmesnik

---

## Namestitev

1. Prenesi **`mmix_setup.exe`** iz zavihka [**Releases**](../../releases/latest).
2. Zaženi namestitveni program – namesti se za trenutnega uporabnika, **brez
   skrbniških pravic**.
3. `mmix` se pojavi v Start meniju; bližnjico na namizju lahko dodaš s kljukico
   med namestitvijo.

Namestitev vključuje tudi odprtje v *Nastavitve → Aplikacije*, kjer ga lahko
kadarkoli odstraniš.

### Prenosna različica

Za prenosno uporabo zadostuje `mmix.exe` iz izdaje – datoteke ne piše v mapo
programa, le imena kanalov shranjuje v
`%APPDATA%\VolumeMixer\names.json` (isto mesto kot izvirnik, zato se imena
ohranijo).

---

## Funkcije

| | |
|---|---|
| 🎚️ **Vse naprave hkrati** | Kartica za vsako aktivno izhodno in vhodno napravo, razvrščena po imenu. |
| 🎛️ **Master kanal** | »Vsi izhodni kanali« – premik ali utišanje masterja vpliva na vse izhode. |
| 📊 **LED peak meter** | 30-segmentni merilnik ravni z barvnimi conami (zelena → rumena → rdeča) in kratkim zadržanjem vrha. |
| 🔇 **Okrogli gumbi za utišanje** | Zeleno jedro = zvok aktiven, rdeče = utišano; moder obroč v barvi `MASTER`. |
| ✏️ **Preimenovanje** | Dvojni klik na ime (ali svinčnik) odpre vnos; ime se shrani trajno. |
| 🔄 **Osveži naprave** | Znova prebere seznam naprav (npr. po priklopu USB slušalk) – brez podvajanja kartic. |
| 🎨 **Temna tema** | Lasten videz: zaobljene kartice, kovinski pravokotni drsniki, mehki prelivi, anti-aliasing prek Pillow. |

### Upravljanje

- **Drsnik** – povleci z miško ali zavrti kolešček nad njim.
- **Odstotek** – klik na vrednost nastavi 100 %.
- **Utišaj** – klik na okrogli gumb.
- **Ime** – dvojni klik za preimenovanje, `Enter` potrdi, `Esc` prekliče.

---

## Izvor projekta

`mmix` je **neodvisna rekonstrukcija** uporabniškega vmesnika in delovanja
starejše slovenske aplikacije *VolumeMixer*, izdelana iz analize izvršljive
datoteke (bytecode) za osebno rabo. To **ni izvirna izvorna koda** in ni
povezano z izvirnim avtorjem.

Videz in ime sta spremenjena (`mmix`, lastna ikona, preoblikovani gumbi in
drsniki), slovenski napisi in osnovna logika (master kanal, merilniki,
shranjevanje imen) pa so ostali enaki, da je aplikacija domača uporabnikom
izvirnika.

---

## Razvoj

### Zahteve

- Python 3.11+ (razvijano na 3.15)
- Windows 10/11

```powershell
pip install -r requirements.txt
```

### Zagon iz izvorne kode

```powershell
python mmix.py
```

### Gradnja samostojnega `.exe`

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name mmix --icon mmicon.ico `
    --add-data "mmicon.ico;." --add-data "mmicon_header.png;." `
    --distpath . --workpath "$env:TEMP\mmix_build\work" `
    --specpath "$env:TEMP\mmix_build" mmix.py
```

> PyInstaller v `.exe` vključi vse potrebno (Python, Tk, pycaw, Pillow), zato
> na ciljnem računalniku ni treba ničesar nameščati. `--onefile` pomeni nekoliko
> počasnejši zagon (razširjanje v začasno mapo).

### Gradnja namestitvenega programa

Potrebuješ [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" mmix_setup.iss
```

Rezultat je `mmix_setup.exe` – namestitev za enega uporabnika v
`%LOCALAPPDATA%\Programs\mmix`, z bližnjicama v Start meniju in (izbirno) na
namizju ter vpisom v *Nastavitve → Aplikacije*. Isti `AppId` omogoča nadgradnjo
brez podvojenih vnosov.

### Struktura

```
mmix.py             # celotna aplikacija (UI + pycaw + renderiranje)
mmix_setup.iss      # skripta za Inno Setup
mmicon.ico          # ikona aplikacije in namestitvenega programa
mmicon_header.png   # logotip v glavi okna
requirements.txt    # Python odvisnosti
docs/               # posnetki za README
```

---

## Znane omejitve

- Aplikacija bere **naprave** (endpointi), ne posameznih programov – tako kot
  izvirnik.
- Peak meter je lahko na nekaterih gonilnikih počasnejši ali manj natančen.
- Brez podpisa kode: Windows SmartScreen lahko ob prvem zagonu pokaže
  opozorilo »Unknown publisher«.

## Licenca

Za zdaj **brez licence** – vse pravice pridržane. Če želiš kodo prosto
uporabljati in spreminjati, predlagam dodajanje licence MIT; odpri issue ali
povej, pa jo dodam.
