"""
mmix - sodoben temen mešalnik glasnosti za vse aktivne avdio naprave (Windows).
Pokončni drsniki z gradientnim polnilom in LED peak meterjem, master kanal,
preimenovanje kanalov, ikona aplikacije in (izbirno) brezrobno okno z neonskim
okvirjem (mapa frame/, glej build_frame.py).

Namestitev:
    pip install pycaw comtypes

Zagon:
    python volume_mixer.py
"""
import json
import math
import os
import sys
import ctypes
import tkinter as tk
import uuid
from ctypes import (POINTER, byref, c_int, c_long, c_uint32, c_void_p, cast,
                    wintypes)

import comtypes
from comtypes import CLSCTX_ALL
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.api.endpointvolume import IAudioEndpointVolume, IAudioMeterInformation
from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
from pycaw.pycaw import (AudioSession, AudioUtilities, IAudioSessionControl2)

E_RENDER = 0
E_CAPTURE = 1
STATE_ACTIVE = 1

FONT = 'Segoe UI'


def F(size, weight=''):
    """Pisava v pikslih (negativna velikost), da videz ne skače pri DPI skaliranju."""
    px = -max(1, round(size * 4 / 3))
    if weight:
        return (FONT, px, weight)
    return (FONT, px)


BG = '#0b0d12'
CARD = '#12161d'
CARD_EDGE = '#202736'
TEXT = '#eef1f7'
SUBTEXT = '#7d879a'
SUBTEXT2 = '#4a5366'
TRACK = '#1c222d'
BTN = '#1c222d'
BTN_HOVER = '#2a3344'
ACCENT = '#38bdf8'
ACCENT_HOVER = '#7dd3fc'
KNOB = '#ffffff'
GREEN = '#34d399'
YELLOW = '#fbbf24'
RED = '#fb7185'

MUTE_RED = '#ef4444'
MUTE_RED_HOVER = '#f86060'
MUTE_GREEN = GREEN
MUTE_GREEN_HOVER = '#6ee7b7'
MUTE_GREEN_TEXT = '#052e16'
# Obroba okroglih gumbov: modra kot napis MASTER (ACCENT).
MUTE_RING = ACCENT
MUTE_RING_HOVER = ACCENT_HOVER


def resource_path(name):
    """Pot do datoteke ob skripti ali (v .exe) v PyInstallerjevi začasni mapi."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def mix(c1, c2, t):
    """Pomeša dve hex barvi (t=0 -> c1, t=1 -> c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# Obroba kanalov med vlečenjem aplikacije: 1 = možna tarča, 2 = izbrana tarča.
DROP_HINT = mix(ACCENT, CARD_EDGE, 0.45)


# Kovinski videz drsnikov: temen rob -> svetlina -> temen rob (žleb)
# oz. svetlo zgoraj -> temno spodaj (ročaj).
STEEL_EDGE = '#0b0e13'
STEEL_STOPS = ((0.00, '#242a33'), (0.15, '#4b5561'), (0.34, '#b6c1cd'),
               (0.50, '#8d98a5'), (0.68, '#5e6772'), (0.86, '#3b434d'),
               (1.00, '#232932'))
KNOB_STOPS = ((0.00, '#f2f7fb'), (0.20, '#d6dfe8'), (0.45, '#abb6c3'),
              (0.65, '#818c9a'), (0.85, '#5a636e'), (1.00, '#383f49'))


def _ramp(stops, n):
    """Vrne n barv, enakomerno interpoliranih med barvnimi postanki."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if t <= p1 + 1e-9:
                k = 0.0 if p1 <= p0 else (t - p0) / (p1 - p0)
                out.append(mix(c0, c1, max(0.0, min(1.0, k))))
                break
        else:
            out.append(stops[-1][1])
    return out


def steel_ramp(n):
    """n navpičnih odtenkov kovinskega žleba."""
    return _ramp(STEEL_STOPS, n)


def metal_rows(h):
    """h vodoravnih odtenkov kovinskega ročaja."""
    return _ramp(KNOB_STOPS, h)


try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

SS = 4  # nadvzorčenje: gumb narišemo 4x večji in pomanjšamo -> gladki robovi


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _shade(color, factor):
    """factor < 1 = temnejša barva, > 1 = svetlejša."""
    r, g, b = _rgb(color)
    return tuple(max(0, min(255, round(v * factor))) for v in (r, g, b))


def _vgrad(w, h, top, bottom):
    """Navpična prelivka RGB."""
    strip = Image.new('RGB', (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return strip.resize((w, h))


def _disc(size, radius):
    """Maska polnega kroga."""
    mask = Image.new('L', (size, size), 0)
    c = size / 2
    ImageDraw.Draw(mask).ellipse([c - radius, c - radius, c + radius, c + radius],
                                 fill=255)
    return mask


def _ring(size, r_out, r_in):
    """Maska obroča (krog z izrezanim središčem)."""
    mask = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(mask)
    c = size / 2
    d.ellipse([c - r_out, c - r_out, c + r_out, c + r_out], fill=255)
    d.ellipse([c - r_in, c - r_in, c + r_in, c + r_in], fill=0)
    return mask


def _pill(size_w, size_h, radius):
    """Maska zaobljenega pravokotnika (pilule)."""
    mask = Image.new('L', (size_w, size_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size_w - 1, size_h - 1],
                                           radius=radius, fill=255)
    return mask


DIM = {c: mix(c, TRACK, 0.62) for c in (GREEN, YELLOW, RED)}

METER_INTERVAL_MS = 40
USE_NEON_FRAME = False
ANIMATE_FRAME = False
HOLD_FALL = 1.0

PROFILES = {
    'headphones': (40, 60),
    'speakers': (60, 80),
    'mic': (70, 90),
    'other': (60, 80),
}

PROFILE_LABELS = {
    'headphones': 'slušalke',
    'speakers': 'zvočniki',
    'mic': 'mikrofon',
    'other': 'naprava',
}

FORM_FACTOR_KEY = '{1da5d803-d492-4edd-8c23-e0c0ffee7f0e} 0'
FORM_FACTOR_PROFILE = {
    1: 'speakers',
    2: 'speakers',
    3: 'headphones',
    4: 'mic',
    5: 'headphones',
    6: 'headphones',
    8: 'speakers',
    9: 'speakers',
}

HEADPHONE_WORDS = ('headphone', 'headset', 'earphone', 'earbud', 'buds', 'airpods',
                   'slušalk', 'hands-free', 'handsfree')
SPEAKER_WORDS = ('speaker', 'zvočnik', 'soundbar', 'hdmi')
MIC_WORDS = ('microphone', 'mikrofon', 'mic ')


def detect_profile(name, direction, device):
    """Določi vrsto naprave: najprej po form factorju, nato po imenu."""
    if direction == 'Vhod':
        return 'mic'
    try:
        props = AudioUtilities.CreateDevice(device).properties
        ff = props.get(FORM_FACTOR_KEY)
        if ff is not None and int(ff) in FORM_FACTOR_PROFILE:
            return FORM_FACTOR_PROFILE[int(ff)]
    except Exception:
        pass
    low = name.lower()
    if any(w in low for w in HEADPHONE_WORDS):
        return 'headphones'
    if any(w in low for w in MIC_WORDS):
        return 'mic'
    if any(w in low for w in SPEAKER_WORDS):
        return 'speakers'
    return 'other'


def level_color(level, profile='other'):
    """Barva glede na glasnost in vrsto naprave, ki predvaja zvok."""
    green_max, yellow_max = PROFILES[profile]
    if level <= green_max:
        return GREEN
    if level <= yellow_max:
        return YELLOW
    return RED


def list_devices():
    """Vrne seznam (ime, smer, glasnost, profil, meter) za vse aktivne naprave."""
    enumerator = comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator,
                                           IMMDeviceEnumerator,
                                           comtypes.CLSCTX_INPROC_SERVER)
    result = []
    for flow, label in ((E_RENDER, 'Izhod'), (E_CAPTURE, 'Vhod')):
        collection = enumerator.EnumAudioEndpoints(flow, STATE_ACTIVE)
        for i in range(collection.GetCount()):
            dev = collection.Item(i)
            try:
                name = AudioUtilities.CreateDevice(dev).FriendlyName
            except Exception:
                name = f'Naprava {i}'
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            try:
                m_iface = dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                meter = cast(m_iface, POINTER(IAudioMeterInformation))
            except Exception:
                meter = None
            try:
                dev_id = dev.GetId()
            except Exception:
                dev_id = f'{label}:{name}'
            result.append((name, label, vol, detect_profile(name, label, dev), meter, dev_id))
    return result


# ---------------------------------------------------------------------------
# Usmerjanje posameznih aplikacij na izbrano izhodno napravo
#
# Windows "privzeto napravo" za posamezno aplikacijo hrani v internem WinRT
# razredu Windows.Media.Internal.AudioPolicyConfig. To je natanko mehanizem,
# ki ga uporablja tudi sistemski mešalnik (Nastavitve > Sistem > Zvok >
# Glasnost mešalnika), zato mmix uporablja isti vmesnik.
# ---------------------------------------------------------------------------
PACK_PREFIX = '\\\\?\\SWD#MMDEVAPI#'
PACK_RENDER = '#{e6327cad-dcec-4949-ae8a-991e976a79d2}'
POLICY_CLASS = 'Windows.Media.Internal.AudioPolicyConfig'
POLICY_IID = 'ab3d4648-e242-459f-b02f-541c70306324'
IID_INSPECTABLE = 'af86e2e0-b12d-4c6a-9c5a-d7aa65101e90'
SESSION_ACTIVE = 1


class _GUID(ctypes.Structure):
    _fields_ = [('Data1', c_uint32), ('Data2', ctypes.c_uint16),
                ('Data3', ctypes.c_uint16), ('Data4', ctypes.c_ubyte * 8)]


def _guid(text):
    return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


def _pack_device(dev_id):
    return PACK_PREFIX + dev_id + PACK_RENDER


def _unpack_device(dev_id):
    if not dev_id:
        return None
    if dev_id.startswith(PACK_PREFIX):
        dev_id = dev_id[len(PACK_PREFIX):]
    if dev_id.endswith(PACK_RENDER):
        dev_id = dev_id[:-len(PACK_RENDER)]
    return dev_id or None


def short_device(name):
    """Kratka oznaka naprave za gumb v vrstici aplikacije."""
    if not name:
        return 'SISTEMSKO'
    return name.split(' (')[0].strip().upper()[:18]


class AudioRouter:
    """Ovoj okoli Windows.Media.Internal.AudioPolicyConfig (surovi vtable).

    Vmesnik ni dokumentiran, zato kličemo metode po zaporednem mestu v tabeli:
    SetPersistedDefaultAudioEndpoint = 25, GetPersistedDefaultAudioEndpoint = 26
    (pred njima je 6 mest za IInspectable in 19 rezerviranih).
    """

    def __init__(self):
        self.ok = False
        self.policy = None
        self._get = None
        self._set = None
        self._create = None
        self._delete = None
        self._raw = None
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            combase = ctypes.WinDLL('combase.dll')
            self._create = combase.WindowsCreateString
            self._create.argtypes = [wintypes.LPCWSTR, c_uint32,
                                     POINTER(c_void_p)]
            self._create.restype = c_long
            self._delete = combase.WindowsDeleteString
            self._delete.argtypes = [c_void_p]
            self._raw = combase.WindowsGetStringRawBuffer
            self._raw.argtypes = [c_void_p, POINTER(c_uint32)]
            self._raw.restype = wintypes.LPCWSTR
            activate = combase.RoGetActivationFactory
            activate.argtypes = [c_void_p, POINTER(_GUID), POINTER(c_void_p)]
            activate.restype = c_long

            name = self._hstring(POLICY_CLASS)
            factory = c_void_p()
            if not name:
                return
            hr = activate(name, byref(_guid(IID_INSPECTABLE)), byref(factory))
            self._delete(name)
            if hr != 0 or not factory:
                return

            query = ctypes.WINFUNCTYPE(
                c_long, c_void_p, POINTER(_GUID), POINTER(c_void_p))(
                self._slot(factory, 0))
            policy = c_void_p()
            hr = query(factory, byref(_guid(POLICY_IID)), byref(policy))
            if hr != 0 or not policy:
                return
            self.policy = policy
            self._set = ctypes.WINFUNCTYPE(
                c_long, c_void_p, c_uint32, c_int, c_int, c_void_p)(
                self._slot(policy, 25))
            self._get = ctypes.WINFUNCTYPE(
                c_long, c_void_p, c_uint32, c_int, c_int, POINTER(c_void_p))(
                self._slot(policy, 26))
            self.ok = self._set is not None and self._get is not None
        except Exception:
            self.ok = False

    @staticmethod
    def _slot(ptr, index):
        return ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents[index]

    def _hstring(self, text):
        handle = c_void_p()
        try:
            if self._create(text, len(text), byref(handle)) != 0:
                return None
        except Exception:
            return None
        return handle

    def get(self, pid):
        """Vrne ID naprave, na katero je aplikacija vezana, ali None."""
        if not self.ok:
            return None
        handle = c_void_p()
        try:
            hr = self._get(self.policy, pid, E_RENDER, 1, byref(handle))
            if hr != 0 or not handle:
                return None
            length = c_uint32(0)
            raw = self._raw(handle, byref(length))
            if not raw:
                return None
            return _unpack_device(raw[:length.value])
        except Exception:
            return None
        finally:
            if handle:
                try:
                    self._delete(handle)
                except Exception:
                    pass

    def set(self, pid, dev_id=None):
        """Nastavi napravo za aplikacijo (None = sistemsko privzeto)."""
        if not self.ok:
            return False
        handle = self._hstring(_pack_device(dev_id)) if dev_id else None
        try:
            multimedia = self._set(self.policy, pid, E_RENDER, 1, handle)
            console = self._set(self.policy, pid, E_RENDER, 0, handle)
        except Exception:
            return False
        finally:
            if handle:
                try:
                    self._delete(handle)
                except Exception:
                    pass
        return multimedia == 0 and console == 0


def list_audio_apps(router, skip_pids=()):
    """Vrne slovar aplikacij, ki trenutno predvajajo zvok.

    Ključ je ime izvršljive datoteke (brez .exe), vrednost pa slovar z imenom,
    seznamom PID-ov (brskalniki imajo več procesov) in izbrano napravo.
    """
    apps = {}
    try:
        devices = AudioUtilities.GetAllDevices(data_flow=E_RENDER,
                                               device_state=STATE_ACTIVE)
    except Exception:
        return apps
    try:
        default_id = AudioUtilities.GetSpeakers().id
    except Exception:
        default_id = None

    for dev in devices:
        try:
            sessions = dev.AudioSessionManager.GetSessionEnumerator()
            count = sessions.GetCount()
        except Exception:
            continue
        for i in range(count):
            try:
                control = sessions.GetSession(i)
                if control is None:
                    continue
                session = AudioSession(control.QueryInterface(
                    IAudioSessionControl2))
                pid = session.ProcessId
            except Exception:
                continue
            if not pid or pid in skip_pids:
                continue
            try:
                if int(session.State) != SESSION_ACTIVE:
                    continue
            except Exception:
                continue
            process = session.Process
            name = ''
            if process is not None:
                try:
                    name = process.name()
                except Exception:
                    name = ''
            if not name:
                name = (session.DisplayName or f'PID {pid}').strip()
            raw_name = name.lower()
            key = raw_name[:-4] if raw_name.endswith('.exe') else raw_name
            display = key or name
            item = apps.setdefault(key, {'name': display, 'pids': [],
                                         'default_id': default_id,
                                         'route': None})
            if pid not in item['pids']:
                item['pids'].append(pid)

    for item in apps.values():
        for pid in item['pids']:
            route = router.get(pid)
            if route:
                item['route'] = route
                break
    return dict(sorted(apps.items()))


class NameStore:
    """Shranjuje imena kanalov, ki jih je uporabnik spremenil (JSON v %APPDATA%)."""

    def __init__(self):
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        self.path = os.path.join(base, 'VolumeMixer', 'names.json')
        self.data = {}
        try:
            with open(self.path, encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data = {str(k): str(v) for k, v in loaded.items()}
        except Exception:
            pass

    def get(self, key, default):
        return self.data.get(key) or default

    def set(self, key, value):
        value = value.strip()
        if value:
            self.data[key] = value
        else:
            self.data.pop(key, None)
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class GroupVolume:
    """Master: skupna glasnost vseh izhodnih naprav (ima enak vmesnik kot IAudioEndpointVolume).

    Prikazuje glasnost najglasnejše naprave. Ko premakneš master, se vse izhodne naprave
    sorazmerno premaknejo, tako da ostanejo razmerja med njimi enaka.
    """

    def __init__(self, vols):
        self.vols = vols
        self._base = None

    def _levels(self):
        out = []
        for v in self.vols:
            try:
                out.append(v.GetMasterVolumeLevelScalar())
            except Exception:
                out.append(0.0)
        return out

    def begin_drag(self):
        self._base = self._levels()

    def end_drag(self):
        self._base = None

    def GetMasterVolumeLevelScalar(self):
        return max(self._levels(), default=0.0)

    def SetMasterVolumeLevelScalar(self, value, ctx):
        base = self._base or self._levels()
        top = max(base, default=0.0)
        for v, b in zip(self.vols, base):
            if top <= 0.001:
                new = value
            else:
                new = value * b / top
            try:
                v.SetMasterVolumeLevelScalar(min(1.0, max(0.0, new)), ctx)
            except Exception:
                pass

    def GetMute(self):
        try:
            return int(bool(self.vols) and all(v.GetMute() for v in self.vols))
        except Exception:
            return 0

    def SetMute(self, muted, ctx):
        for v in self.vols:
            try:
                v.SetMute(muted, ctx)
            except Exception:
                pass


class GroupMeter:
    """Peak master mešalnika: najvišji peak med vsemi izhodnimi napravami."""

    def __init__(self, meters):
        self.meters = [m for m in meters if m is not None]

    def GetPeakValue(self):
        peak = 0.0
        for m in self.meters:
            try:
                peak = max(peak, m.GetPeakValue())
            except Exception:
                pass
        return peak


class FlatButton(tk.Label):
    """Ploščat gumb z hover učinkom."""

    def __init__(self, parent, text, command, bg=BTN, hover=BTN_HOVER, fg=TEXT,
                 font=F(9, 'bold'), padx=16, pady=6):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx,
                         pady=pady, cursor='hand2')
        self.command = command
        self.base, self.hover, self._hovering = bg, hover, False
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', lambda e: self.command())

    def _enter(self, _):
        self._hovering = True
        self.config(bg=self.hover)

    def _leave(self, _):
        self._hovering = False
        self.config(bg=self.base)

    def restyle(self, bg, hover, fg, text=None):
        self.base, self.hover = bg, hover
        self.config(bg=hover if self._hovering else bg, fg=fg)
        if text is not None:
            self.config(text=text)


MAX_NAME = 28


def short_name(name):
    """Dolga imena naprav skrajša, da kartica ostane ozka."""
    if len(name) <= MAX_NAME:
        return name
    return name[:MAX_NAME - 1].rstrip() + '…'


class RoundedCard(tk.Canvas):
    """Zaobljeno polje (kartica), v katero damo vsebino prek .inner."""

    RADIUS = 20
    PAD = 6

    def __init__(self, parent, accent=False, group=None, fill=CARD,
                 radius=None, auto=True):
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0)
        self.accent = accent
        self.fill = fill
        self.highlight = 0
        self._size = None
        self.group = group if group is not None else []
        self.group.append(self)
        if radius is not None:
            self.RADIUS = radius
        self.inner = tk.Frame(self, bg=fill)
        self.win = self.create_window(self.PAD, self.PAD, window=self.inner, anchor='nw')
        if auto:
            self.inner.bind('<Configure>', lambda e: self.fit())

    def fit(self):
        members = [c for c in self.group if c.winfo_exists()]
        if not members:
            return
        w = max(c.inner.winfo_reqwidth() for c in members) + 2 * self.PAD
        h = max(c.inner.winfo_reqheight() for c in members) + 2 * self.PAD
        for c in members:
            c.apply(w, h)

    def set_highlight(self, level=0):
        """0 = običajno, 1 = možna tarča, 2 = tarča pod kazalcem."""
        if level == self.highlight:
            return
        self.highlight = level
        if self._size:
            w, h = self._size
            self._size = None
            self.apply(w, h)

    def apply(self, w, h):
        if self._size == (w, h):
            return
        self._size = (w, h)
        self.config(width=w, height=h)
        self.itemconfig(self.win, width=w - 2 * self.PAD, height=h - 2 * self.PAD)
        self.delete('bg')
        x0, y0, x1, y1, r = 1, 1, w - 1, h - 1, self.RADIUS
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        if self.highlight >= 2:
            outline, width = ACCENT, 2
        elif self.highlight == 1:
            outline, width = DROP_HINT, 1
        elif self.accent:
            outline, width = mix(ACCENT, self.fill, 0.25), 2
        else:
            outline, width = CARD_EDGE, 1
        self.create_polygon(pts, smooth=True, fill=self.fill, tags='bg',
                            outline=outline, width=width)
        if self.highlight >= 2:
            sheen = ACCENT
        elif self.accent:
            sheen = mix(ACCENT, self.fill, 0.45)
        else:
            sheen = mix(self.fill, '#ffffff', 0.07)
        self.create_line(x0 + r, y0 + 2, x1 - r, y0 + 2, fill=sheen, tags='bg')
        self.tag_lower('bg')


class PillButton(tk.Canvas):
    """Gumb v obliki pilule. Privzeto je poln (barvna prelivka), z ``ghost=True``
    pa je temen z izrazito obrobo in napisom v barvi obrobe."""

    def __init__(self, parent, text, command, bg, hover, fg='#ffffff',
                 width=64, height=24, font=None, parent_bg=CARD,
                 ghost=False, fg_hover=None, radius=None):
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.w, self.h = width, height
        self.command = command
        self.font = font or F(9, 'bold')
        self.base, self.hover, self.fg, self.text = bg, hover, fg, text
        self.ghost = ghost
        self.fg_hover = fg_hover
        self.radius = radius
        self._hovering = False
        self.bind('<Enter>', lambda e: self._set_hover(True))
        self.bind('<Leave>', lambda e: self._set_hover(False))
        self.bind('<Button-1>', lambda e: self.command())
        self.draw()

    def _set_hover(self, value):
        self._hovering = value
        self.draw()

    def draw(self):
        self.delete('all')
        if HAVE_PIL:
            self._img = ImageTk.PhotoImage(self.render_image(), master=self)
            self.create_image(0, 0, image=self._img, anchor='nw')
        elif self.ghost:
            w, h, r = self.w, self.h, self.radius or self.h / 2
            fill = '#111c26'
            edge = self.hover if self._hovering else self.base
            pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h,
                   w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
            self.create_polygon(pts, smooth=True, fill=fill, outline=edge, width=2)
        else:
            w, h = self.w, self.h
            fill = self.hover if self._hovering else self.base
            self.create_oval(0, 0, w, h, fill=fill, outline='')
            self.create_oval(w - h, 0, w, h, fill=fill, outline='')
            self.create_rectangle(h / 2, 0, w - h / 2, h, fill=fill, outline='')
        color = self.fg_hover if (self._hovering and self.fg_hover) else self.fg
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=color,
                         font=self.font)

    def render_image(self):
        """Gladek gumb (nadvzorčen, LANCZOS); poln ali obroben (ghost)."""
        w, h = self.w, self.h
        nw, nh = w * SS, h * SS
        rad = self.radius if self.radius is not None else h / 2
        nrad = rad * SS
        if self.ghost:
            return self._render_ghost(nw, nh, nrad, w, h)
        fill = self.hover if self._hovering else self.base
        mask = _pill(nw, nh, nrad)
        img = Image.new('RGBA', (nw, nh), (0, 0, 0, 0))
        img.paste(_vgrad(nw, nh, _shade(fill, 1.22), _shade(fill, 0.84)).convert('RGBA'),
                  (0, 0), mask)
        sheen = Image.new('RGBA', (nw, nh), (0, 0, 0, 0))
        ImageDraw.Draw(sheen).rounded_rectangle(
            [SS * 2, SS * 1.5, nw - 1 - SS * 2, nh * 0.46], radius=nrad,
            outline=(255, 255, 255, 42), width=SS)
        sheen.putalpha(ImageChops.multiply(sheen.getchannel('A'), mask))
        img.alpha_composite(sheen)
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, nw - 1, nh - 1], radius=nrad,
            outline=_shade(fill, 0.50) + (255,), width=SS)
        return img.resize((w, h), Image.LANCZOS)

    def _render_ghost(self, nw, nh, nrad, w, h):
        """Temno telo z modro obrobo, mehkim sijajem in nežno senco."""
        edge = self.hover if self._hovering else self.base
        body = mix('#0f1a23', edge, 0.20 if self._hovering else 0.10)
        mask = Image.new('L', (nw, nh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, nw - 1, nh - 1],
                                               radius=nrad, fill=255)
        img = Image.new('RGBA', (nw, nh), (0, 0, 0, 0))
        img.paste(_vgrad(nw, nh, _shade(body, 1.20), _shade(body, 0.86)).convert('RGBA'),
                  (0, 0), mask)

        glow = Image.new('RGBA', (nw, nh), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle(
            [SS, SS, nw - 1 - SS, nh - 1 - SS], radius=nrad,
            outline=_rgb(edge) + (95 if self._hovering else 55,), width=2 * SS)
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(1.6 * SS)))

        sheen = Image.new('RGBA', (nw, nh), (0, 0, 0, 0))
        ImageDraw.Draw(sheen).rounded_rectangle(
            [SS * 3, SS * 2.2, nw - 1 - SS * 3, nh * 0.50], radius=nrad,
            outline=_rgb(edge) + (55,), width=SS)
        sheen.putalpha(ImageChops.multiply(sheen.getchannel('A'), mask))
        img.alpha_composite(sheen)

        ImageDraw.Draw(img).rounded_rectangle(
            [SS, SS, nw - 1 - SS, nh - 1 - SS], radius=nrad,
            outline=_rgb(edge) + (255,), width=int(1.5 * SS))
        return img.resize((w, h), Image.LANCZOS)

    def restyle(self, bg, hover, fg, text=None):
        self.base, self.hover, self.fg = bg, hover, fg
        if text is not None:
            self.text = text
        self.draw()


class MuteButton(tk.Canvas):
    """Okrogel gumb za utišanje: zunanji obroč je vedno moder (kot napis
    MASTER), notranji krog pa gori zeleno, ko je zvok aktiven, in je rdeč,
    ko je kanal utišan."""

    SIZE = 34

    def __init__(self, parent, command, active=True, parent_bg=CARD):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.command = command
        self.active = active
        self._hovering = False
        self._img = None
        self.bind('<Enter>', lambda e: self._set_hover(True))
        self.bind('<Leave>', lambda e: self._set_hover(False))
        self.bind('<Button-1>', lambda e: self.command())
        self.draw()

    def _set_hover(self, value):
        self._hovering = value
        self.draw()

    def set_active(self, active):
        """active=True -> notranji krog je zelen, False -> rdeč."""
        if active == self.active:
            return
        self.active = active
        self.draw()

    def draw(self):
        self.delete('all')
        if HAVE_PIL:
            self._img = ImageTk.PhotoImage(self.render_image(), master=self)
            self.create_image(0, 0, image=self._img, anchor='nw')
            return
        s = self.SIZE
        cx = cy = s / 2
        ring = MUTE_RING_HOVER if self._hovering else MUTE_RING
        self.create_oval(1.5, 1.5, s - 1.5, s - 1.5, outline=ring, width=3)
        if self.active:
            fill = MUTE_GREEN_HOVER if self._hovering else MUTE_GREEN
        else:
            fill = MUTE_RED_HOVER if self._hovering else MUTE_RED
        r = s / 2 - 6
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline='')
        icon = MUTE_GREEN_TEXT if self.active else '#ffffff'
        u = r * 0.85
        self.create_polygon(cx - 0.5 * u, cy - 0.22 * u, cx - 0.22 * u, cy - 0.22 * u,
                            cx + 0.09 * u, cy - 0.58 * u, cx + 0.09 * u, cy + 0.58 * u,
                            cx - 0.22 * u, cy + 0.22 * u, cx - 0.5 * u, cy + 0.22 * u,
                            fill=icon, outline='')
        if self.active:
            self.create_arc(cx, cy - 0.5 * u, cx + 0.62 * u, cy + 0.5 * u,
                            start=-55, extent=110, style='arc', outline=icon, width=2)
        else:
            self.create_line(cx - 0.62 * u, cy + 0.62 * u, cx + 0.62 * u, cy - 0.62 * u,
                             fill=icon, width=2)

    def render_image(self):
        """Gladek okrogel gumb: moder obroč (kot napis MASTER), notranji krog z
        radialno prelivko, mehka senca, odsev in anti-aliased simbol zvočnika."""
        s = self.SIZE
        n = s * SS
        c = n / 2
        r_out = (s / 2 - 1.0) * SS
        r_in = r_out - 3.0 * SS
        r_core = r_in - 1.5 * SS
        hover = self._hovering

        ring_top = _shade(MUTE_RING_HOVER, 1.05 if hover else 0.98)
        ring_bot = _shade(MUTE_RING, 0.74 if hover else 0.62)
        if self.active:
            core_in = _shade(MUTE_GREEN_HOVER, 1.06 if hover else 0.96)
            core_out = _shade(MUTE_GREEN, 0.62)
            glyph = _rgb(MUTE_GREEN_TEXT)
        else:
            core_in = _shade(MUTE_RED_HOVER, 1.06 if hover else 0.96)
            core_out = _shade(MUTE_RED, 0.60)
            glyph = (255, 255, 255)

        img = Image.new('RGBA', (n, n), (0, 0, 0, 0))

        shadow = Image.new('RGBA', (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse(
            [c - r_out, c - r_out + 1.4 * SS, c + r_out, c + r_out + 1.4 * SS],
            fill=(0, 0, 0, 120))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.5 * SS)))

        img.paste(_vgrad(n, n, ring_top, ring_bot).convert('RGBA'), (0, 0),
                  _ring(n, r_out, r_in))

        grad = Image.radial_gradient('L').resize((n, n), Image.BICUBIC)
        core = Image.composite(Image.new('RGB', (n, n), core_out),
                               Image.new('RGB', (n, n), core_in), grad)
        img.paste(core.convert('RGBA'), (0, 0), _disc(n, r_core))

        gloss = Image.new('RGBA', (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(gloss).ellipse(
            [c - r_core * 0.62, c - r_core * 0.88, c + r_core * 0.30, c - r_core * 0.02],
            fill=(255, 255, 255, 80 if self.active else 60))
        gloss = gloss.filter(ImageFilter.GaussianBlur(r_core * 0.16))
        gloss.putalpha(ImageChops.multiply(gloss.getchannel('A'), _disc(n, r_core)))
        img.alpha_composite(gloss)

        d = ImageDraw.Draw(img)
        u = r_core * 0.92
        lw = max(2, int(u * 0.10))
        d.polygon([(c - 0.46 * u, c - 0.20 * u), (c - 0.20 * u, c - 0.20 * u),
                   (c + 0.08 * u, c - 0.54 * u), (c + 0.08 * u, c + 0.54 * u),
                   (c - 0.20 * u, c + 0.20 * u), (c - 0.46 * u, c + 0.20 * u)],
                  fill=glyph)
        if self.active:
            d.arc([c + 0.04 * u, c - 0.44 * u, c + 0.60 * u, c + 0.44 * u],
                  -55, 55, fill=glyph, width=lw)
            d.arc([c + 0.04 * u, c - 0.76 * u, c + 0.94 * u, c + 0.76 * u],
                  -50, 50, fill=glyph, width=lw)
        else:
            d.line([(c - 0.60 * u, c + 0.60 * u), (c + 0.60 * u, c - 0.60 * u)],
                   fill=glyph, width=lw)

        return img.resize((s, s), Image.LANCZOS)


CHIP_FILL = mix(CARD, '#ffffff', 0.05)
CHIP_W = 182
CHIP_H = 56
APPS_COLS = 6


class AppChip:
    """Ena aplikacija v spodnji plošči: povleci jo na kanal ali klikni gumb."""

    def __init__(self, parent, app, route_text, on_pick, panel=None):
        self.app = app
        self.panel = panel
        self.card = RoundedCard(parent, group=[], fill=CHIP_FILL, radius=11,
                                auto=False)
        self.card.apply(CHIP_W, CHIP_H)
        body = self.card.inner
        head = tk.Frame(body, bg=CHIP_FILL)
        head.pack(fill='x', padx=2)
        self.grip = tk.Canvas(head, width=10, height=16, bg=CHIP_FILL,
                              highlightthickness=0, bd=0, cursor='fleur')
        for row in range(3):
            for col in range(2):
                self.grip.create_oval(2 + col * 4, 3 + row * 4,
                                      4 + col * 4, 5 + row * 4,
                                      fill=SUBTEXT2, outline='')
        self.grip.pack(side='left', padx=(0, 4))
        name = app['name']
        if len(name) > 20:
            name = name[:19].rstrip() + '\u2026'
        self.name = tk.Label(head, text=name, bg=CHIP_FILL, fg=TEXT,
                             font=F(9, 'bold'), anchor='w', cursor='fleur')
        self.name.pack(side='left', fill='x', expand=True)
        self.button = PillButton(
            body, route_text, lambda: on_pick(self), ACCENT, ACCENT_HOVER,
            fg=ACCENT, fg_hover='#e8f7ff', width=CHIP_W - 28, height=21,
            font=F(8, 'bold'), parent_bg=CHIP_FILL, ghost=True, radius=7)
        self.button.pack(pady=(3, 0))

        for widget in (self.card, body, head, self.grip, self.name):
            widget.bind('<ButtonPress-1>', self._press)
            widget.bind('<B1-Motion>', self._motion)
            widget.bind('<ButtonRelease-1>', self._release)

    # -- vlečenje na kanal ------------------------------------------------
    def _press(self, event):
        if self.panel is not None:
            self.panel.drag_start(self, event)
        return 'break'

    def _motion(self, event):
        if self.panel is not None:
            self.panel.drag_move(event)
        return 'break'

    def _release(self, event):
        if self.panel is not None:
            self.panel.drag_end(event)
        return 'break'


class AppsPanel:
    """Plošča pod napravami: katere aplikacije predvajajo zvok in kam."""

    def __init__(self, parent, router, devices, columns=()):
        self.router = router
        self.devices = list(devices)
        self._columns = list(columns)
        self._apps = {}
        self._sig = None
        self.chips = []
        self._cols = APPS_COLS
        self._width = 0
        self._menu = None
        self._drag = None
        self._status_job = None
        self._empty = 0
        self.shell = RoundedCard(parent, group=[], auto=False)
        host = self.shell.inner

        head = tk.Frame(host, bg=CARD)
        head.pack(fill='x', padx=14, pady=(6, 0))
        tk.Label(head, text='APLIKACIJE', bg=CARD, fg=ACCENT,
                 font=F(10, 'bold')).pack(side='left')
        tk.Label(head, text='predvajajo zvok', bg=CARD, fg=SUBTEXT,
                 font=F(9)).pack(side='left', padx=(8, 0))
        self.status = tk.Label(head, text='', bg=CARD, fg=SUBTEXT,
                               font=F(9), anchor='e')
        self.status.pack(side='right')
        if not router.ok:
            self.status.config(text='Usmerjanje ni podprto', fg=YELLOW)

        self.grid = tk.Frame(host, bg=CARD)
        self.grid.pack(fill='x', padx=10, pady=(5, 0))
        self.hint = tk.Label(
            host, text='Povleci aplikacijo na kanal · klik na gumb odpre seznam '
                       '· MASTER pomeni sistemsko privzeto',
            bg=CARD, fg=SUBTEXT2, font=F(8), anchor='w')
        self.hint.pack(fill='x', padx=14, pady=(3, 6))

    # -- razporeditev -----------------------------------------------------
    def resize(self, width):
        if width <= 0:
            return
        if width != self._width:
            self._width = width
            cols = max(1, min(APPS_COLS, (width - 24) // (CHIP_W + 6)))
            if cols != self._cols:
                self._cols = cols
                self._sig = None
        self.refresh(force=True)

    def set_devices(self, devices):
        if devices != self.devices:
            self.devices = list(devices)
            self._sig = None

    def set_columns(self, columns):
        if self._drag:
            self.drag_cancel()
        self._columns = [c for c in columns if getattr(c, 'shell', None)]
        self._sig = None

    def device_name(self, dev_id):
        for did, name in self.devices:
            if did == dev_id:
                return name
        return None

    def route_text(self, app):
        route = app.get('route')
        if not route:
            return 'SISTEMSKO'
        name = self.device_name(route)
        return short_device(name) if name else 'DRUGA'

    # -- vsebina ----------------------------------------------------------
    def refresh(self, force=False):
        if (self._menu is not None or self._drag is not None) and not force:
            return
        apps = list_audio_apps(self.router, skip_pids={os.getpid()})
        if not apps and self._apps:
            # Kratkotrajen izpad (npr. Windows med premikom sejo na novo ustvari)
            # ne sme povzročiti utripanja plošče.
            self._empty += 1
            if self._empty < 2:
                return
        else:
            self._empty = 0
        sig = tuple((key, tuple(app['pids']), app.get('route'))
                    for key, app in apps.items())
        if not force and sig == self._sig:
            return
        self._sig = sig
        self._apps = apps

        for child in self.grid.winfo_children():
            child.destroy()
        self.chips = []
        chips = list(apps.values())
        if not chips:
            tk.Label(self.grid, text='Trenutno ne predvaja nobena aplikacija.',
                     bg=CARD, fg=SUBTEXT2, font=F(9), anchor='w').grid(
                row=0, column=0, sticky='w', padx=4, pady=4)
            rows = 1
        else:
            for index, app in enumerate(chips):
                chip = AppChip(self.grid, app, self.route_text(app),
                               self.open_menu, self)
                chip.card.grid(row=index // self._cols, column=index % self._cols,
                               padx=3, pady=3)
                self.chips.append(chip)
            rows = (len(chips) + self._cols - 1) // self._cols
        if self._width:
            height = 38 + rows * (CHIP_H + 6) + 18
            self.shell.apply(self._width, height)

    def set_status(self, text, color=SUBTEXT):
        self.status.config(text=text, fg=color)
        if self._status_job:
            try:
                self.after_cancel(self._status_job)
            except Exception:
                pass
            self._status_job = None
        if text:
            self._status_job = self.status.after(
                7000, lambda: self.status.config(text=''))

    # -- vlečenje aplikacije na kanal -------------------------------------
    def _drop_columns(self):
        cols = []
        for col in self._columns:
            shell = getattr(col, 'shell', None)
            if shell is None or getattr(col, 'direction', None) != 'Izhod':
                continue
            cols.append(col)
        return cols

    def _target_at(self, x_root, y_root):
        for col in self._drop_columns():
            shell = col.shell
            try:
                x0, y0 = shell.winfo_rootx(), shell.winfo_rooty()
                if (x0 <= x_root <= x0 + shell.winfo_width() and
                        y0 <= y_root <= y0 + shell.winfo_height()):
                    return col
            except tk.TclError:
                continue
        return None

    def _target_text(self, col):
        if col is None:
            return 'izberi kanal'
        if getattr(col, 'is_master', False):
            return 'SISTEMSKO'
        return short_menu_name(getattr(col, 'full_name', 'kanal'))

    def _highlight(self, active=None):
        for col in self._drop_columns():
            col.shell.set_highlight(2 if col is active else 1)

    def _clear_highlights(self):
        for col in self._columns:
            shell = getattr(col, 'shell', None)
            if shell is None:
                continue
            try:
                shell.set_highlight(0)
            except tk.TclError:
                pass

    def drag_start(self, chip, event):
        self.close_menu()
        if not self.router.ok:
            self.set_status('Usmerjanje ni podprto na tem sistemu', YELLOW)
            return
        self.drag_cancel()
        self._drag = {'app': chip.app, 'x': event.x_root, 'y': event.y_root,
                      'active': False, 'target': None, 'ghost': None,
                      'arrow': None}

    def drag_move(self, event):
        drag = self._drag
        if drag is None:
            return
        if not drag['active']:
            if (abs(event.x_root - drag['x']) < 6 and
                    abs(event.y_root - drag['y']) < 6):
                return
            self._begin_ghost(drag)
        self._move_ghost(drag, event)
        target = self._target_at(event.x_root, event.y_root)
        if target is not drag['target']:
            drag['target'] = target
            self._highlight(target)
            if drag['arrow'] is not None:
                drag['arrow'].config(text='\u2192 ' + self._target_text(target))
            if target is None:
                self.set_status('Spusti na kanal z izhodno napravo', SUBTEXT)
            else:
                self.set_status('Spusti na ' + self._target_text(target), ACCENT)

    def drag_end(self, event):
        drag = self._drag
        if drag is None:
            return
        self._drag = None
        target = drag['target']
        if drag['active']:
            target = self._target_at(event.x_root, event.y_root)
        self._drop_ghost(drag)
        self._clear_highlights()
        if not drag['active']:
            return
        if target is None:
            self.set_status('Premik preklican – spusti na kanal', SUBTEXT)
            self.refresh(force=True)
            return
        self.apply(drag['app'],
                   None if getattr(target, 'is_master', False) else target.key)

    def drag_cancel(self):
        drag = self._drag
        self._drag = None
        if drag is not None:
            self._drop_ghost(drag)
        self._clear_highlights()

    def _begin_ghost(self, drag):
        win = tk.Toplevel(self.shell)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=BG)
        try:
            win.attributes('-topmost', True)
            win.attributes('-alpha', 0.96)
        except Exception:
            pass
        card = RoundedCard(win, group=[], fill=CHIP_FILL, radius=10, auto=False)
        card.pack()
        card.apply(238, 50)
        name = drag['app']['name']
        if len(name) > 26:
            name = name[:25].rstrip() + '\u2026'
        tk.Label(card.inner, text=name, bg=CHIP_FILL, fg=TEXT,
                 font=F(9, 'bold'), anchor='w').pack(fill='x', padx=2)
        arrow = tk.Label(card.inner, text='\u2192 izberi kanal', bg=CHIP_FILL,
                         fg=ACCENT, font=F(8, 'bold'), anchor='w')
        arrow.pack(fill='x', padx=2, pady=(1, 0))
        drag['ghost'] = win
        drag['arrow'] = arrow
        drag['active'] = True
        x = drag['x'] + 16
        y = drag['y'] + 14
        win.geometry(f'+{x}+{y}')
        win.deiconify()
        win.lift()
        self._highlight(drag['target'])
        self.set_status('Spusti na kanal z izhodno napravo', SUBTEXT)

    def _move_ghost(self, drag, event):
        win = drag['ghost']
        if win is None:
            return
        x = event.x_root + 16 if event is not None else drag['x'] + 16
        y = event.y_root + 14 if event is not None else drag['y'] + 14
        x = max(8, min(x, win.winfo_screenwidth() - 246))
        y = max(8, min(y, win.winfo_screenheight() - 58))
        win.geometry(f'+{x}+{y}')

    def _drop_ghost(self, drag):
        win = drag.get('ghost')
        drag['ghost'] = None
        drag['arrow'] = None
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass

    # -- izbira naprave ---------------------------------------------------
    def open_menu(self, chip):
        self.close_menu()
        app = chip.app
        win = tk.Toplevel(chip.button)
        win.withdraw()
        win.overrideredirect(True)
        win.configure(bg=BG)
        try:
            win.attributes('-topmost', True)
        except Exception:
            pass
        body = tk.Frame(win, bg=BG)
        body.pack(fill='both', expand=True, padx=1, pady=1)
        current = app.get('route')
        entries = [(None, 'Sistemsko privzeto')]
        entries += [(dev_id, name) for dev_id, name in self.devices]
        for index, (dev_id, name) in enumerate(entries):
            if index == 1:
                tk.Frame(body, bg=CARD_EDGE, height=1).pack(fill='x', pady=3)
            mark = '\u2713' if (dev_id or None) == (current or None) else ' '
            label = tk.Label(
                body, text=f'{mark}  {short_menu_name(name)}', bg=BG, fg=TEXT,
                font=F(9), anchor='w', padx=10, pady=5)
            label.pack(fill='x')
            label.bind('<Enter>', lambda e, w=label: w.config(bg=BTN_HOVER))
            label.bind('<Leave>', lambda e, w=label: w.config(bg=BG))
            label.bind('<Button-1>',
                       lambda e, d=dev_id, a=app: self._choose(a, d))

        win.update_idletasks()
        height = body.winfo_reqheight() + 2
        width = max(240, body.winfo_reqwidth() + 2)
        x = chip.button.winfo_rootx()
        y = chip.button.winfo_rooty() + chip.button.winfo_height() + 4
        screen_w = self.shell.winfo_screenwidth()
        screen_h = self.shell.winfo_screenheight()
        x = max(8, min(x, screen_w - width - 8))
        if y + height > screen_h - 8:
            y = chip.button.winfo_rooty() - height - 4
        y = max(8, y)
        win.geometry(f'{width}x{height}+{x}+{y}')
        win.deiconify()
        win.lift()
        win.grab_set()
        win.bind('<Escape>', lambda e: self.close_menu())
        win.bind('<Button-1>', lambda e: self.close_menu())
        self._menu = win

    def close_menu(self):
        win = self._menu
        self._menu = None
        if win is not None:
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

    def _choose(self, app, dev_id):
        self.close_menu()
        self.apply(app, dev_id)
        return 'break'

    def apply(self, app, dev_id):
        if not self.router.ok:
            self.set_status('Usmerjanje ni podprto na tem sistemu', RED)
            return
        moved = 0
        for pid in app['pids']:
            if self.router.set(pid, dev_id):
                moved += 1
        label = short_device(self.device_name(dev_id)) if dev_id else 'SISTEMSKO'
        if moved:
            self.set_status(f"{app['name']} \u2192 {label}", ACCENT)
        else:
            self.set_status('Aplikacija trenutno ne predvaja zvoka', RED)
        self.refresh(force=True)


def short_menu_name(name):
    if len(name) <= 38:
        return name
    return name[:37].rstrip() + '\u2026'


def draw_device_icon(c, kind, color):
    """Vektorska ikona naprave (26x26 px), narisana s platnom."""
    c.delete('all')

    if kind == 'headphones':
        c.create_arc(5, 4, 21, 20, start=0, extent=180, style='arc',
                     outline=color, width=2)
        c.create_rectangle(4, 12, 9, 20, fill=color, outline=color)
        c.create_rectangle(17, 12, 22, 20, fill=color, outline=color)
        return

    if kind == 'mic':
        c.create_oval(10, 3, 16, 9, fill=color, outline=color)
        c.create_rectangle(10, 6, 16, 12, fill=color, outline=color)
        c.create_oval(10, 9, 16, 15, fill=color, outline=color)
        c.create_arc(7, 7, 19, 19, start=180, extent=180, style='arc',
                     outline=color, width=2)
        c.create_line(13, 19, 13, 23, fill=color, width=2)
        c.create_line(9, 23, 17, 23, fill=color, width=2)
        return

    if kind == 'master':
        for x, yk in ((7, 16), (13, 9), (19, 15)):
            c.create_line(x, 4, x, 22, fill=mix(color, CARD, 0.55), width=2)
            c.create_oval(x - 3, yk - 3, x + 3, yk + 3, fill=color, outline=color)
        return

    c.create_polygon(4, 10, 8, 10, 13, 5, 13, 21, 8, 16, 4, 16,
                     fill=color, outline=color)
    c.create_arc(11, 8, 20, 18, start=-55, extent=110, style='arc',
                 outline=color, width=2)
    c.create_arc(10, 4, 24, 22, start=-55, extent=110, style='arc',
                 outline=color, width=2)


class DeviceColumn(tk.Frame):
    """Kartica: ikona in ime, drsnik z LED peak meterjem, odstotek in gumb Utišaj."""

    CANVAS_W = 52
    TRACK_TOP = 12
    TRACK_H = 150
    TRACK_W = 10
    CX = 34
    KNOB_W = 20
    KNOB_H = 13
    SEGMENTS = 30

    def __init__(self, parent, name, direction, vol, profile, meter,
                 master=False, on_change=None, key=None, names=None):
        super().__init__(parent, bg=CARD, padx=4, pady=4)
        self.shell = None
        self.is_master = master
        self.direction = direction
        self.key = key
        self.names = names
        self.default_name = name
        self.entry = None
        self.on_change = on_change
        self.vol = vol
        self.profile = profile
        self.meter = meter
        self.dragging = False
        self.volume = vol.GetMasterVolumeLevelScalar() * 100
        self.muted = bool(vol.GetMute())
        self.level = 0.0
        self.hold = 0.0
        tint = ACCENT if master else SUBTEXT

        self.icon = tk.Canvas(self, width=26, height=26, bg=CARD, highlightthickness=0)
        self.icon.pack(pady=(2, 0))
        draw_device_icon(self.icon, 'master' if master else profile, tint)

        tk.Label(self, text='MASTER' if master else direction.upper(), bg=CARD, fg=tint,
                 font=F(7, 'bold')).pack(pady=(1, 3))

        shown = names.get(key, name) if names and key else name
        self.full_name = shown
        self.name_box = tk.Frame(self, bg=CARD)
        self.name_box.pack()
        self.name_lbl = tk.Label(self.name_box, text=short_name(shown), bg=CARD, fg=TEXT,
                                 font=F(9), wraplength=56, justify='center', cursor='hand2')
        self.edit_icon = tk.Label(self.name_box, text='✎', bg=CARD, fg=SUBTEXT2,
                                  font=F(9), cursor='hand2')
        self.name_lbl.pack(side='left')
        self.edit_icon.pack(side='left', padx=(4, 0))
        self.name_lbl.bind('<Double-Button-1>', lambda e: self.start_rename())
        self.edit_icon.bind('<Button-1>', lambda e: self.start_rename())
        self.edit_icon.bind('<Enter>', lambda e: self.edit_icon.config(fg=ACCENT))
        self.edit_icon.bind('<Leave>', lambda e: self.edit_icon.config(fg=SUBTEXT2))

        self.canvas = tk.Canvas(self, width=self.CANVAS_W,
                                height=self.TRACK_H + 2 * self.TRACK_TOP,
                                bg=CARD, highlightthickness=0, cursor='hand2')
        self.canvas.pack(pady=(8, 2))
        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.canvas.bind('<MouseWheel>', self.on_wheel)

        self.pct = tk.Label(self, bg=CARD, fg=TEXT, font=F(17, 'bold'), width=4)
        self.pct.pack()
        self.mute_btn = MuteButton(self, self.on_mute, active=not self.muted)
        self.mute_btn.pack(pady=(2, 2))
        self.style_mute()
        self.draw()

    def y_of(self, pct):
        return self.TRACK_TOP + self.TRACK_H * (1 - pct / 100)

    def pct_of(self, y):
        pct = (self.TRACK_TOP + self.TRACK_H - y) / self.TRACK_H * 100
        return max(0.0, min(100.0, pct))

    def zone_color(self, pct):
        """Barva pri danem % z mehkim prehodom med conami (zelena, rumena, rdeča)."""
        g, y = PROFILES[self.profile]
        t = 4.0
        if pct <= g - t:
            return GREEN
        if pct < g + t:
            return mix(GREEN, YELLOW, (pct - (g - t)) / (2 * t))
        if pct <= y - t:
            return YELLOW
        if pct < y + t:
            return mix(YELLOW, RED, (pct - (y - t)) / (2 * t))
        return RED

    def draw(self):
        """Nariše žleb, gradientno polnilo, skalo in ročaj; nato še peak meter."""
        c = self.canvas
        c.delete('all')
        cx, tw = self.CX, self.TRACK_W
        top_y = self.TRACK_TOP
        bot_y = self.TRACK_TOP + self.TRACK_H
        vol = self.volume

        self.level = min(self.level, vol)
        self.hold = min(self.hold, vol)

        for p in (0, 25, 50, 75, 100):
            y = self.y_of(p)
            c.create_line(21, y, 24 if p % 50 == 0 else 26, y, fill=SUBTEXT2)
            if p % 50 == 0:
                c.create_text(17, y, text=str(p), anchor='e', fill=SUBTEXT2, font=F(7))

        # Žleb: pravokoten kovinski kanal (brez zaobljenih robov).
        x0 = cx - tw / 2
        for i, col in enumerate(steel_ramp(tw)):
            c.create_rectangle(x0 + i, top_y, x0 + i + 1, bot_y,
                               fill=col, outline='')
        c.create_rectangle(x0 - 1, top_y - 1, x0 + tw + 1, bot_y + 1,
                           outline=STEEL_EDGE)
        c.create_line(x0, top_y + 1, x0 + tw, top_y + 1, fill='#1a1f27')

        # Polnilo: barva cone v kovinskem odtenku + robna svetloba/senca.
        hy = self.y_of(vol)
        hw = tw / 2 - 2
        y = bot_y
        while y > hy + 0.5:
            y2 = max(hy, y - 3)
            base = TRACK if self.muted else mix(
                self.zone_color(self.pct_of((y + y2) / 2)), TRACK, 0.55)
            c.create_rectangle(cx - hw, y2, cx + hw, y, fill=base, outline='')
            c.create_line(cx - hw, y2, cx - hw, y, fill=mix(base, '#ffffff', 0.35))
            c.create_line(cx + hw, y2, cx + hw, y, fill=mix(base, '#000000', 0.40))
            y = y2

        # Ročaj: pravokoten kovinski drsnik s prelivko in barvno oznako cone.
        ring = SUBTEXT if self.muted else level_color(vol, self.profile)
        left, right = cx - self.KNOB_W / 2, cx + self.KNOB_W / 2
        top, bot = hy - self.KNOB_H / 2, hy + self.KNOB_H / 2
        c.create_rectangle(left + 1, top + 2, right + 1, bot + 2,
                           fill='#070a0e', outline='', tags='knob')
        for i, col in enumerate(metal_rows(self.KNOB_H)):
            c.create_rectangle(left, top + i, right, top + i + 1,
                               fill=col, outline='', tags='knob')
        c.create_rectangle(left, top, right, bot, outline=STEEL_EDGE, tags='knob')
        for gx in (left + 4.5, right - 4.5):
            c.create_line(gx, top + 2.5, gx, bot - 2.5,
                          fill='#6d7784', tags='knob')
        c.create_rectangle(left + 3, hy - 1.5, right - 3, hy + 1.5,
                           fill=ring, outline='', tags='knob')
        c.create_line(left + 2, top + 1.5, right - 2, top + 1.5,
                      fill='#ffffff', tags='knob')
        self.pct.config(text=f'{int(round(vol))}%',
                        fg=SUBTEXT if self.muted else ring)
        self.draw_meter()

    def draw_meter(self):
        """LED peak meter znotraj žleba: segmenti sežejo največ do ročaja."""
        c = self.canvas
        c.delete('meter')
        if self.muted:
            return
        cx, n = self.CX, self.SEGMENTS
        for i in range(n):
            hi = (i + 1) / n * 100
            lo = i / n * 100
            if lo >= self.volume:
                break
            if (lo + hi) / 2 <= self.level:
                c.create_rectangle(cx - 2, self.y_of(hi) + 1, cx + 2, self.y_of(lo),
                                   fill=self.zone_color((lo + hi) / 2),
                                   outline='', tags='meter')
        if self.hold > 0.5:
            y = self.y_of(self.hold)
            c.create_rectangle(cx - 2, y - 1, cx + 2, y + 1,
                               fill=KNOB, outline='', tags='meter')
        c.tag_lower('meter', 'knob')

    def style_mute(self):
        self.mute_btn.set_active(not self.muted)

    def start_rename(self):
        """Dvojni klik na ime (ali klik na svinčnik) odpre vnos novega imena."""
        if self.entry is not None:
            return
        self.name_lbl.pack_forget()
        self.edit_icon.pack_forget()
        self.entry = tk.Entry(self.name_box, font=F(9), justify='center', width=10,
                              bg=BTN, fg=TEXT, insertbackground=TEXT, relief='flat',
                              highlightthickness=1, highlightbackground=ACCENT,
                              highlightcolor=ACCENT)
        self.entry.insert(0, self.full_name)
        self.entry.select_range(0, 'end')
        self.entry.pack(ipady=3)
        self.entry.focus_force()
        self.entry.bind('<Return>', lambda e: self.finish_rename(True))
        self.entry.bind('<Escape>', lambda e: self.finish_rename(False))
        self.entry.bind('<FocusOut>', lambda e: self.finish_rename(True))

    def finish_rename(self, save):
        entry = self.entry
        if entry is None:
            return
        self.entry = None
        new = entry.get().strip()
        entry.destroy()
        if save and self.names is not None and self.key:
            self.names.set(self.key, new)
            self.full_name = new or self.default_name
            self.name_lbl.config(text=short_name(self.full_name))
        self.name_lbl.pack(side='left')
        self.edit_icon.pack(side='left', padx=(4, 0))

    def set_volume(self, pct):
        self.volume = max(0.0, min(100.0, pct))
        try:
            self.vol.SetMasterVolumeLevelScalar(self.volume / 100, None)
        except Exception:
            pass
        self.draw()
        if self.on_change:
            self.on_change(self)

    def on_press(self, e):
        self.dragging = True
        begin = getattr(self.vol, 'begin_drag', None)
        if begin:
            begin()
        self.set_volume(self.pct_of(e.y))

    def on_drag(self, e):
        self.set_volume(self.pct_of(e.y))

    def on_release(self, _):
        self.dragging = False
        end = getattr(self.vol, 'end_drag', None)
        if end:
            end()

    def on_wheel(self, e):
        begin = getattr(self.vol, 'begin_drag', None)
        if begin:
            begin()
        self.set_volume(self.volume + (2 if e.delta > 0 else -2))
        end = getattr(self.vol, 'end_drag', None)
        if end:
            end()

    def on_mute(self):
        self.muted = not self.muted
        try:
            self.vol.SetMute(int(self.muted), None)
        except Exception:
            pass
        self.style_mute()
        self.draw()
        if self.on_change:
            self.on_change(self)

    def update_meter(self):
        """Peak (linearna amplituda) je na isti skali kot drsnik, zato kaže do ročaja.
        Hiter vzpon in mehko padanje dasta gladko gibanje."""
        if self.meter is None:
            return
        try:
            peak = self.meter.GetPeakValue()
        except Exception:
            peak = 0.0
        target = min(max(peak * 100, 0.0), self.volume)
        if self.level >= target:
            self.level = target
        else:
            self.level = max(target, self.level - max(1.2, (self.level - target) * 0.18))
        self.hold = min(max(self.level, self.hold - HOLD_FALL), self.volume)
        self.draw_meter()

    def refresh(self):
        """Sinhronizira UI, če je glasnost spremenjena od drugod."""
        try:
            volume = self.vol.GetMasterVolumeLevelScalar() * 100
            muted = bool(self.vol.GetMute())
            changed = abs(volume - self.volume) > 0.05 or muted != self.muted
            self.volume = volume
            if muted != self.muted:
                self.muted = muted
                self.style_mute()
            if changed:
                self.draw()
        except Exception:
            return


def colorref(hex_color):
    """#rrggbb -> Windows COLORREF (0x00BBGGRR)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return (b << 16) | (g << 8) | r


def dark_titlebar(win):
    """Temna naslovna vrstica; na Windows 11 še barva ozadja, roba in besedila."""
    try:
        import ctypes
        win.update()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        dwm = ctypes.windll.dwmapi

        def set_attr(attr, value):
            try:
                v = ctypes.c_int(value)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v),
                                          ctypes.sizeof(v))
            except Exception:
                pass

        for attr in (20, 19):
            set_attr(attr, 1)
        set_attr(35, colorref(BG))
        set_attr(34, colorref(CARD_EDGE))
        set_attr(36, colorref(TEXT))
    except Exception:
        pass


def enable_dpi_awareness():
    """Brez tega Windows okno z visokim DPI poveča in zamegli (okvir bi bil prevelik)."""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def set_app_id():
    """Svoj ID aplikacije, da opravilna vrstica pokaže našo ikono, ne Pythonove."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('JBJ.mmix')
    except Exception:
        pass


def load_frame_meta():
    """Prebere frame/meta.json (naredi ga build_frame.py). None = okvira ni."""
    folder = resource_path('frame')
    try:
        with open(os.path.join(folder, 'meta.json'), encoding='utf-8') as f:
            meta = json.load(f)
        meta['dir'] = folder
        return meta
    except Exception:
        return None


class App(tk.Tk):
    def __init__(self):
        global FONT, BG
        super().__init__()
        self.title('mmix')
        try:
            self.iconbitmap(resource_path('mmicon.ico'))
        except Exception:
            pass
        try:
            from tkinter import font as tkfont
            fams = set(tkfont.families(self))
            for cand in ('Segoe UI Variable Text', 'Segoe UI Variable', 'Segoe UI'):
                if cand in fams:
                    FONT = cand
                    break
        except Exception:
            pass
        self.configure(bg=BG)
        self.resizable(False, False)
        self.columns = []
        self.cards = []
        self.names = NameStore()
        self.router = AudioRouter()
        self.apps_panel = None
        self._apps_timer = None
        self.meta = load_frame_meta() if USE_NEON_FRAME else None
        if self.meta:
            BG = self.meta['bg']
            self.configure(bg=BG)
        self.frames = []
        self.frame_i = 0
        self._drag = (0, 0)
        self._minimized = False
        if self.meta:
            try:
                for i in range(self.meta['frames'] if ANIMATE_FRAME else 1):
                    self.frames.append(tk.PhotoImage(
                        file=os.path.join(self.meta['dir'], f'f{i:02d}.png')))
            except tk.TclError:
                self.meta, self.frames = None, []
        if self.meta:
            self.build_framed_window()
        else:
            self.resizable(True, False)
            self.content = tk.Frame(self, bg=BG, padx=10, pady=6)
            self.content.pack(fill='both', expand=True)
        self.build_topbar()
        self.holder = tk.Frame(self.content, bg=BG)
        self.holder.pack(expand=True)
        self.build()
        if not self.meta:
            dark_titlebar(self)
        self.after(1000, self.poll)
        self.after(METER_INTERVAL_MS, self.poll_meters)

    def build_framed_window(self):
        m = self.meta
        W, H = m['w'], m['h']
        x0, y0, x1, y1 = m['inner']
        key = m['key']
        self.configure(bg=key)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 2)}')
        self.canvas = tk.Canvas(self, width=W, height=H, bg=key, highlightthickness=0)
        self.canvas.place(x=0, y=0)
        self.bg_item = self.canvas.create_image(0, 0, image=self.frames[0], anchor='nw')
        self.canvas.bind('<ButtonPress-1>', self.start_move)
        self.canvas.bind('<B1-Motion>', self.do_move)
        self.content = tk.Frame(self, bg=BG)
        self.content.place(x=x0, y=y0, width=x1 - x0, height=y1 - y0)
        self.bind('<Map>', self.on_map)
        self.make_borderless()
        if ANIMATE_FRAME and len(self.frames) > 1:
            self.after(int(1000 / m.get('fps', 20)), self.animate)

    def make_borderless(self):
        self.overrideredirect(True)
        try:
            self.wm_attributes('-transparentcolor', self.meta['key'])
        except tk.TclError:
            pass
        self.after(60, self.show_in_taskbar)

    def show_in_taskbar(self):
        """overrideredirect skrije gumb v opravilni vrstici; to ga vrne (Windows)."""
        try:
            import ctypes
            GWL_EXSTYLE, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW = -20, 0x40000, 0x80
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                  (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
            self.withdraw()
            self.after(40, self.deiconify)
        except Exception:
            pass

    def animate(self):
        self.frame_i = (self.frame_i + 1) % len(self.frames)
        self.canvas.itemconfig(self.bg_item, image=self.frames[self.frame_i])
        self.after(int(1000 / self.meta['fps']), self.animate)

    def start_move(self, e):
        self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def do_move(self, e):
        self.geometry(f'+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}')

    def minimize(self):
        self._minimized = True
        self.overrideredirect(False)
        self.iconify()

    def on_map(self, e):
        if e.widget is self and self._minimized:
            self._minimized = False
            self.after(20, self.make_borderless)

    def build_topbar(self):
        bar = tk.Frame(self.content, bg=BG, padx=14, pady=10)
        bar.pack(fill='x')
        left = tk.Frame(bar, bg=BG)
        left.pack(side='left')
        try:
            self.logo = tk.PhotoImage(file=resource_path('mmicon_header.png'))
            logo = tk.Label(left, image=self.logo, bg=BG)
            logo.pack(side='left', padx=(0, 10))
        except Exception:
            logo = None
        text = tk.Frame(left, bg=BG)
        text.pack(side='left')
        title = tk.Label(text, text='mmix', bg=BG, fg=TEXT, font=F(15, 'bold'))
        title.pack(anchor='w')
        sub = tk.Label(text, text='Glasnost, peak meter in usmerjanje aplikacij',
                       bg=BG, fg=SUBTEXT, font=F(9))
        sub.pack(anchor='w')
        if self.meta:
            FlatButton(bar, '✕', self.destroy, hover=RED, fg=TEXT,
                       padx=11, pady=3).pack(side='right', padx=(6, 0))
            FlatButton(bar, '—', self.minimize, padx=11, pady=3).pack(
                side='right', padx=(6, 0))
            for w in (bar, left, text, title, sub, logo):
                if w is None:
                    continue
                w.bind('<ButtonPress-1>', self.start_move)
                w.bind('<B1-Motion>', self.do_move)
        PillButton(bar, 'Osveži naprave', self.build, ACCENT, ACCENT_HOVER,
                   fg=ACCENT, fg_hover='#e8f7ff', width=128, height=30,
                   font=F(9, 'bold'), parent_bg=BG, ghost=True,
                   radius=9).pack(side='right')

    def poll_meters(self):
        for c in self.columns:
            c.update_meter()
        self.after(METER_INTERVAL_MS, self.poll_meters)

    def build(self):
        # Najprej odstranimo obstoječe kartice (in z njimi vsebino), sicer bi se
        # ob vsakem osveževanju v holder dodala še ena kopija naprav.
        for card in list(self.cards):
            try:
                if card.winfo_exists():
                    card.destroy()
            except tk.TclError:
                pass
        for c in list(self.columns):
            try:
                if c.winfo_exists():
                    c.destroy()
            except tk.TclError:
                pass
        self.columns.clear()
        self.cards.clear()
        devices = list_devices()
        outputs = [d for d in devices if d[1] == 'Izhod']
        if outputs:
            shell = RoundedCard(self.holder, accent=True, group=self.cards)
            master = DeviceColumn(
                shell.inner, 'Vsi izhodni kanali', 'Izhod',
                GroupVolume([d[2] for d in outputs]),
                'other',
                GroupMeter([d[4] for d in outputs]),
                master=True, on_change=self.sync_columns, key='__master__',
                names=self.names)
            master.shell = shell
            master.pack(fill='both', expand=True)
            shell.pack(side='left', padx=5, pady=4)
            self.columns.append(master)
        for name, direction, vol, profile, meter, dev_id in devices:
            shell = RoundedCard(self.holder, group=self.cards)
            col = DeviceColumn(shell.inner, name, direction, vol, profile, meter,
                               on_change=self.sync_columns, key=dev_id,
                               names=self.names)
            col.shell = shell
            col.pack(fill='both', expand=True)
            shell.pack(side='left', padx=5, pady=4)
            self.columns.append(col)
        if self.apps_panel is not None:
            self.apps_panel.set_columns(self.columns)
        self.sync_apps_panel()

    def output_devices(self):
        try:
            return [(d.id, d.FriendlyName) for d in AudioUtilities.GetAllDevices(
                data_flow=E_RENDER, device_state=STATE_ACTIVE)]
        except Exception:
            return []

    def sync_apps_panel(self):
        devices = self.output_devices()
        if self.apps_panel is None:
            self.apps_panel = AppsPanel(self.content, self.router, devices,
                                        self.columns)
            self.apps_panel.shell.pack(pady=(6, 0))
        else:
            self.apps_panel.set_devices(devices)
            self.apps_panel.set_columns(self.columns)
        self.update_idletasks()
        self.apps_panel.resize(self.holder.winfo_reqwidth())
        if self._apps_timer is None:
            self._apps_timer = self.after(1500, self.poll_apps)

    def poll_apps(self):
        self._apps_timer = None
        if self.apps_panel is not None:
            self.apps_panel.refresh()
            self._apps_timer = self.after(1500, self.poll_apps)

    def sync_columns(self, source):
        """Ko se spremeni eden kanal, osveži ostale (npr. master ob premiku naprave)."""
        for c in self.columns:
            if c is not source and not c.dragging:
                c.refresh()

    def poll(self):
        for c in self.columns:
            if not c.dragging:
                c.refresh()
        self.after(1000, self.poll)


if __name__ == '__main__':
    set_app_id()
    enable_dpi_awareness()
    App().mainloop()
