#!/usr/bin/python3
# **************************************************************************************************************
#
# Internetradio mit einem Raspberry Pi und aufgefuehrter Hardware
# ***************************************************************
#                    Uwe Berger; 2024
#
#
# Hardware (Raspberry-Pin-Belegung in BCM; insgesamt)
# ===================================================
# 
# Drehimpulsgeber (https://cdn.shopify.com/s/files/1/1509/1638/files/Drehimpulsgeber_Modul_Datenblatt.pdf?349756184529908641) 
#
# Encoder Volume
# --------------
# DT        27
# CLK       17
# SW        22
# GND, 3.3V
#
# Encoder Volume
# --------------
# DT        05
# CLK       06
# SW        25
# GND, 3.3V
#
# Audio-HAT (https://www.waveshare.com/wiki/WM8960_Audio_HAT)
# -----------------------------------------------------------
# SDA       02 (SDA)
# SCL       03 (SCL)
# CLK	    18
# LRCLK	    19
# DAC	    21
# ADC	    20
# BUTTON    17 (optional)
# GND, 5V
#
# TFT (ST7735, analog dockerpi...)
# --------------
# SCK   11 (CLK)
# SDA   10 (MISO)
# RES   24
# RS    23
# CS    08 (CE0)
# LEDA  3.3V            <-- eventuell via PWM (Helligkeit)?
# GND, 5V
#
#
# Bedienungelemente/-funktionen
# =============================
#
# Encoder "Volume":
# -----------------
# * Drucktaster     --> Radio an/aus
# * mit Uhrzeiger   --> Lautstaerke lauter
# * gegen Uhrzeiger --> Lautstaerke leiser
#
# Encoder "Selection":
# -----------------
# * Drucktaster     --> wenn Stationsliste angezeigt wird --> selektierte Station uebernehmen
#                   --> wenn ein Hauptbildschirm angezeigt wird --> zum naechsten wechseln ("rundum")
# * mit Uhrzeiger   --> Stationsliste anzeigen --> Selektion nach unten
# * gegen Uhrzeiger --> Stationsliste anzeigen --> Selektion nach oben
#
#
# 
# Struktur Sqlite3-Datenbank (stations.db) mit Beispiel
# =====================================================
#
# Tabelle stations
# ----------------
#    {
#    "changeuuid":"960e57c8-0601-11e8-ae97-52543be04c81",
#    "stationuuid":"960e57c5-0601-11e8-ae97-52543be04c81",
#    "name":"SRF 1",
#    "url":"http://stream.srg-ssr.ch/m/drs1/mp3_128",
#    "url_resolved":"http://stream.srg-ssr.ch/m/drs1/mp3_128",
#    "homepage":"http://ww.srf.ch/radio-srf-1",
#    "favicon":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Radio_SRF_1.svg/205px-Radio_SRF_1.svg.png",
#    "tags":"srg ssr,public radio",
#    "country":"Switzerland",
#    "countrycode":"CH",
#    "state":"",
#    "language":"german",
#    "votes":0,
#    "lastchangetime":"2019-12-12 18:37:02",
#    "codec":"MP3",
#    "bitrate":128,
#    "hls":0,
#    "lastcheckok":1,
#    "lastchecktime":"2020-01-09 18:16:35",
#    "lastcheckoktime":"2020-01-09 18:16:35",
#    "lastlocalchecktime":"2020-01-08 23:18:38",
#    "clicktimestamp":"",
#    "clickcount":0,
#    "clicktrend":0
#    }
#
# Tabelle stations
# ----------------
#    {
#    "stationuuid":"960e57c5-0601-11e8-ae97-52543be04c81",
#    } 
#
#
# notwendige Python-Module
# ========================
# 
# moeglichst fehlende Python-Module via apt installieren,
# damit sie systemweit zur Verfuegung stehen; z.B.:
#  sudo apt install python3-<modulname>
#
# ansonsten via pip installieren:
#  pip install --break-system-packages textwrapper
#  pip install --break-system-packages st7735
#  pip install --break-system-packages gpiodevice
#
#
# ToDo:
# =====
#
# * was ist mit den Falschfarben beim Logo?
# * anderes Default-Logo?
# * haben wir ein Problem, wenn weniger Stationen vorhanden sind als 
#   als der Index in den Settings adressiert...?
# * ein Gehauuse :-)
#
#
# ---------
# Have fun!
#
# ************************************************************************************************************'''

import RPi.GPIO as GPIO

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor

import st7735

import time
from time import sleep
from datetime import datetime

import textwrap

import os
import signal

import json

import sqlite3

from urllib.request import urlopen

import vlc
from vlc import Meta


# BCM-Pins Drehenimpulsgeber
VOLUME_DT_PIN = 27
VOLUME_CLK_PIN = 17
VOLUME_SW_PIN = 22
SELECTION_DT_PIN = 6
SELECTION_CLK_PIN = 5
SELECTION_SW_PIN = 25


# Fonts
FONT_NORMAL = "/usr/share/fontstruetype/dejavu/DejaVuSans.ttf"
FONT_BOLD   = "/usr/share/fontstruetype/dejavu/DejaVuSans-Bold.ttf"

VOLUME_MAX = 100
VOLUME_MIN = 0

MAIN_SCREENS = 4

TIMEOUT_CLOSE_WINDOW = 5000 # ms
REFRESH_MEDIA_INFOS  = 5000 # ms

# Default, wenn keine sqlite3-DB da ist bzw. nicht sinnvolles drin ist
stations = [
    {"name" : "Altrockmetal-Radiogirls", "url" : "http://stream.laut.fm/altrockmetal-radiogirls", "favicon" : ""},
    {"name" : "Best Net Radio - 80s Metal", "url" : "http://bigrradio-edge1.cdnstream.com/5146_128", "favicon" : ""},
    {"name" : "Digital Impulse - Heavy Metal", "url" : "http://orion.shoutca.st:8165/", "favicon" : ""},
    {"name" : "METAL HEART RADIO", "url" : "http://fr.radio-streamhosting.com:8000/metalheartradio128mp3", "favicon" : ""},
    {"name" : "Ostrock und Ostpop", "url" : "https://topradio-de-hz-fal-stream07-cluster01.radiohost.de/brf-ostrock-pop_mp3-128", "favicon" : "https://upload.berliner-rundfunk.de/production/static/1675427710513/icons/icon_64.a80y02808w0.png"},
    {"name" : "Philly Rock Radio", "url" : "http://streaming.live365.com/a77620", "favicon" : "http://www.phillyrockradio.com/uploads/6/6/3/9/6639316/published/alexa.png?1609898590"},
    {"name" : "RADIO BOB! - Symphonic Metal", "url" : "https://streams.radiobob.de/symphmetal/mp3-192/streams.radiobob.de/", "favicon" : ""},
    {"name" : "RADIO BOB! BOBs Christmas Rock", "url" : "http://streams.radiobob.de/bob-christmas/mp3-192/streams.radiobob.de/", "favicon" : ""},
    {"name" : "RADIO BOB! BOBs Wacken Nonstop (192kbit)", "url" : "http://streams.radiobob.de/bob-wacken/mp3-192/streams.radiobob.de/", "favicon" : "http://www.phillyrockradio.com/uploads/6/6/3/9/6639316/published/alexa.png?1609898590"},
    {"name" : "RPR1.Heavy Metal", "url" : "http://streams.rpr1.de/rpr-metal-128-mp3", "favicon" : ""},
    {"name" : "Radio Bob! M. Sammet", "url" : "http://streams.radiobob.de/sammet/mp3-192/mediaplayer/", "favicon" : ""},
    {"name" : "Radio Ostrock", "url" : "http://secondradio.de:7070/ostrock", "favicon" : "https://www.radio-ostrock.de/webcfg/apple-icon-120x120.png"},
    {"name" : "Rock Antenne - Heavy Metal", "url" : "http://mp3channels.webradio.rockantenne.de/heavy-metal", "favicon" : "http://www.rockantenne.de/logos/rock-antenne/apple-touch-icon.png"},
    {"name" : "Rock antenne soft Rock (64)", "url" : "http://mp3channels.webradio.rockantenne.de/soft-rock.aac", "favicon" : ""},
    {"name" : "Rockantenne Symphonic-Rock", "url" : "|http://stream.rockantenne.de/symphonic-rock/stream/mp3", "favicon" : "https://www.rockantenne.de/logos/rock-antenne/apple-touch-icon.png"},
]
STATIONS_COUNT = len(stations)

# Setting-Defaults 
config = {
            "volume"        : 50,
            "station_idx"   : 0
}

# Anzahl sichtbare Stationen in Stationsauswahlliste
STATION_LIST_MAX_COUNT = 6

# temporaere Werte
temps = {
            "application_on"        : False,           
            "station_list_top"      : 0,
            "station_list_bottom"   : STATION_LIST_MAX_COUNT,
            "station_list_idx"      : 0,
            "main_screen_idx"       : 0,
            "station_list"          : False
}

# Konfiguration "Task" im Main-Loop
cycles = {
            "display_main"              : {"time" : 0, "start" : False},
            "display_app_off"           : {"time" : 0, "start" : True},
            "display_volume"            : {"time" : 0, "start" : False},
            "display_stations"          : {"time" : 0, "start" : False},
            "reset_temp_station_idx"    : {"time" : 0, "start" : False},
            "display_media_infos"       : {"time" : 0, "start" : False},
}

# Verzeichnisse/Dateien
SCRIPT_PATH     = os.path.split(os.path.abspath(__file__))[0]
STATION_DB_FILE = F"{SCRIPT_PATH}/stations.db"
PATH_LOGO_CACHE = F"{SCRIPT_PATH}/logo_cache/"
DEFAULT_LOGO    = F"{SCRIPT_PATH}/icon_radio.png"
SETTINGS_FILE   = F"{SCRIPT_PATH}/iradio.json"

# Farben
COLOR_TEXT_NORMAL                   = 0xffffff
COLOR_BACKGROUND_NORMAL             = 0x000000

COLOR_BACKGROUND_CLOCK_BAR          = 0x2f4f4f
COLOR_TEXT_CLOCK_BAR                = 0xffffff

COLOR_BACKGROUND_WINDOW             = 0x000000
COLOR_FRAME_WINDOW                  = 0x2f4f4f
COLOR_BACKGROUND_LABEL_WINDOW       = 0x2f4f4f
COLOR_TEXT_LABEL_WINDOW             = 0xffffff
COLOR_VOLUME_BAR                    = 0x0000ff
COLOR_TEXT_WINDOW                   = 0xffffff
COLOR_TEXT_SELECTED_STATION         = 0x000000
COLOR_BACKGROUND_SELECTED_STATION   = 0xffffff


# ******************************************************************
def signal_handler(SignalNumber,Frame):
    settings_write()
    player_stop()
    GPIO.cleanup()
    exit()

# ******************************************************************
# Idee: https://github.com/bablokb/simple-dab-radio/blob/master/files/usr/local/sbin/simple-dab-radio.py
def settings_read():
    sname = os.path.expanduser(SETTINGS_FILE)
    if os.path.exists(sname):
        with open(sname,"r") as f:
            settings = json.load(f)
        config["volume"] = settings['volume']
        config["station_idx"] = settings['station_idx']
        temps["station_list_idx"] = config["station_idx"]
        # ...fuer den seltenen Fall, dass eingelesener Index groesser ist, als die tatsaechliche Anzahl der Stationen
        if (config["station_idx"] >= STATIONS_COUNT):
            config["station_idx"] = 0
            temps["station_list_idx"] = config["station_idx"]
      
# ******************************************************************
# Idee: https://github.com/bablokb/simple-dab-radio/blob/master/files/usr/local/sbin/simple-dab-radio.py
def settings_write():
    settings = {
        'volume' : config["volume"],
        'station_idx': config["station_idx"],
        'station_name': stations[config['station_idx']]['name'],
    }
    # ~ sname = os.path.expanduser(SETTINGS_FILE)
    sname = SETTINGS_FILE
    print("saving settings to: %s" % sname)
    with open(sname,"w") as f:
        json.dump(settings,f,indent=2)

# ******************************************************************
def player_setup():
    global vlc_instance, player
    
    vlc_instance = vlc.Instance('--input-repeat=-1', '--fullscreen')
    player=vlc_instance.media_player_new()

# ******************************************************************
def player_start():
    global media, player, vlc_instance
    media=vlc_instance.media_new(stations[config['station_idx']]['url'])
    media.get_mrl()
    player.set_media(media)
    player.audio_set_volume(config["volume"])
    # ~ player.audio_set_volume(70)
    player.play()

# ******************************************************************
def player_stop():
    global player
    player.stop()

# ******************************************************************
def player_set_volume():
    global player
    player.audio_set_volume(config["volume"])

# ******************************************************************
def sql_execute(sql):
    l = []
    try:
        db=sqlite3.connect(STATION_DB_FILE)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        result = cursor.execute(sql)
        for row in result:
            l.append(row)
        db.commit()
        db.close()
    except:
        print("No station-db, load default stations!")
    return l

# ***********************************************************************************************
def load_stations():
    global stations, STATIONS_COUNT
    temp_stations = sql_execute("select * from stations where stationuuid in (select stationuuid from favorites) order by name")
    if len(temp_stations) > 0:
        stations = temp_stations
        STATIONS_COUNT = len(stations)
        # ...fuer den seltenen Fall, dass weniger Stationen eingelesen wurden, als der aktuelle interne Index meint
        if (config["station_idx"] >= STATIONS_COUNT):
            config["station_idx"] = 0
            temps["station_list_idx"] = config["station_idx"]

# ***********************************************************************************************
def load_webimage(url, dx, dy, logo_name, cache_path, default_logo):
    # Datei schon im Cache?
    if os.path.isfile(f"{cache_path}{logo_name}.png"):
        # ja, dann von dort laden
        im = Image.open(f"{cache_path}{logo_name}.png")
    else:
        # nein, dann von URL laden
        try:
            im = Image.open(urlopen(url))
            im.save(f"{cache_path}{logo_name}.png")
        except:
            # URL ist keine Bilddatei, also Default-Logo laden
            im = Image.open(F"{default_logo}")
    # Groesse des Logo entsprechend (dx, dy) anpassen 
    im_x = im.width
    im_y = im.height
    if im_x != dx:
        im_y = round(im_y * dx/im_x)
        im_x = dx
    if im_y != dy:
        im_x = round(im_x * dy/im_y)
        im_y = dy
    im = im.resize((im_x, im_y), Image.LANCZOS)
    # irgendetwas stimmt nicht mit den Farben!?!?! ...dehalb erstmal Graustufen...
    return im.convert("L") # ??? --> https://pillow.readthedocs.io/en/stable/handbook/concepts.html#concept-modes

# ***********************************************************************************************
def time_ms():
    return time.time_ns()/1000000

# ***********************************************************************************************
def seconds_to_next_minute():
    t = int(time.time())
    return 60 - (t - (int(t / 60) * 60))


# ***********************************************************************************************
def cycle_start(name, time, on):
    cycles[name]["time"] = time
    cycles[name]["start"] = on
    
# ***********************************************************************************************
def cycle_stop(name):
    cycles[name]["start"] = False

# ***********************************************************************************************
def cycle_must_run(name):
    if ((cycles[name]["time"] <= time_ms()) and (cycles[name]["start"] == True)):
        return True
    else:
        return False

# ***********************************************************************************************
def encoder_volume(direction):
    
    # radio on/off
    if (direction == 0):
        temps["application_on"] = not temps["application_on"]
        if temps["application_on"]:
            temps["main_screen_idx"] = 0
            load_stations()                 # Stationen neu einlesen
            settings_read()                 # Settings einlesen
            cycle_stop("display_app_off")
            cycle_start("display_main", 0 , True)
            cycle_start("display_media_infos", time_ms() + 20000 , True)
            player_start()
        else:
            cycle_stop("display_main")
            cycle_stop("display_volume")
            cycle_stop("display_stations")
            cycle_stop("reset_temp_station_idx")
            cycle_stop("display_media_infos")
            cycle_start("display_app_off", 0 , True)
            player_stop()
            settings_write()                # Settings schreiben
            pass
        return
        
    if temps["application_on"]:
        if (direction < 0):
            if (config["volume"] >= 5):
                config["volume"] = config["volume"] - 5
            else:
                config["volume"] = 0
        elif (direction > 0):
            if (config["volume"] <= 95):
                config["volume"] = config["volume"] + 5
            else:
                config["volume"] = 100
        player_set_volume()
        cycle_start("display_volume", 0 , True)

# ***********************************************************************************************
def encoder_selection(direction):
    
    if temps["application_on"]:
        if (direction == 0):
            # Button zum Umschalten Screen oder Auswahl Station?
            if temps["station_list"]:
                config["station_idx"] = temps["station_list_idx"]
                temps["main_screen_idx"] = 0
                # ~ player_stop()
                player_start()
                cycle_stop("reset_temp_station_idx")
            else:
                temps["main_screen_idx"] = (temps["main_screen_idx"] + 1) % MAIN_SCREENS
            cycle_start("display_main", 0, True)
            return
            
        if (direction < 0):
            if (temps["station_list_idx"] > 0):
                temps["station_list_idx"] = temps["station_list_idx"] - 1
        elif (direction > 0):
            if (temps["station_list_idx"] < (STATIONS_COUNT - 1)):
                temps["station_list_idx"] = temps["station_list_idx"] + 1
        cycle_start("display_stations", 0 , True)

# ***********************************************************************************************
def encoder_event(pin):
    
    # Volume
    if (pin == VOLUME_DT_PIN):
        if (GPIO.input(VOLUME_DT_PIN) == 1) and (GPIO.input(VOLUME_CLK_PIN) == 0):
            encoder_volume(1)
         
    elif (pin == VOLUME_CLK_PIN):
        if (GPIO.input(VOLUME_DT_PIN) == 0) and (GPIO.input(VOLUME_CLK_PIN) == 1):
            encoder_volume(-1)

    elif (pin == VOLUME_SW_PIN):
        if (GPIO.input(VOLUME_SW_PIN) == 0):
            encoder_volume(0)
    
    # Selection
    elif (pin == SELECTION_DT_PIN):
        if (GPIO.input(SELECTION_DT_PIN) == 1) and (GPIO.input(SELECTION_CLK_PIN) == 0):
            encoder_selection(1)
         
    elif (pin == SELECTION_CLK_PIN):
        if (GPIO.input(SELECTION_DT_PIN) == 0) and (GPIO.input(SELECTION_CLK_PIN) == 1):
            encoder_selection(-1)

    elif (pin == SELECTION_SW_PIN):
        if (GPIO.input(SELECTION_SW_PIN) == 0):
            encoder_selection(0)

# ***********************************************************************************************
def encoder_setup():
    GPIO.setmode(GPIO.BCM)
    # Volume
    GPIO.setup(VOLUME_DT_PIN, GPIO.IN)
    GPIO.setup(VOLUME_CLK_PIN, GPIO.IN)
    GPIO.add_event_detect(VOLUME_DT_PIN, GPIO.RISING, callback=encoder_event, bouncetime=1)
    GPIO.add_event_detect(VOLUME_CLK_PIN, GPIO.RISING, callback=encoder_event, bouncetime=1)
    GPIO.setup(VOLUME_SW_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(VOLUME_SW_PIN, GPIO.FALLING, callback=encoder_event, bouncetime=10)
    # Selection
    GPIO.setup(SELECTION_DT_PIN, GPIO.IN)
    GPIO.setup(SELECTION_CLK_PIN, GPIO.IN)
    GPIO.add_event_detect(SELECTION_DT_PIN, GPIO.RISING, callback=encoder_event, bouncetime=1)
    GPIO.add_event_detect(SELECTION_CLK_PIN, GPIO.RISING, callback=encoder_event, bouncetime=1)
    GPIO.setup(SELECTION_SW_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(SELECTION_SW_PIN, GPIO.FALLING, callback=encoder_event, bouncetime=10)
 
# ***********************************************************************************************
def tft_setup(): 
    global disp, draw, font, font_b, font_20, font_20_b,img, WIDTH, HEIGHT
    disp = st7735.ST7735(port=0, cs=0, dc=23, rst=24, width=128, height=160, rotation=0, offset_left=0, offset_top=0, invert=False)
    disp.begin()
    WIDTH = disp.width
    HEIGHT = disp.height
    img = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    draw.fontmode = "L"   
    font = ImageFont.truetype(FONT_NORMAL, size=11)
    font_b = ImageFont.truetype(FONT_BOLD, size=11)
    font_20 = ImageFont.truetype(FONT_NORMAL, size=20)
    font_20_b = ImageFont.truetype(FONT_BOLD, size=20)

# ***********************************************************************************************
def tft_display_main(): 
    # Bildschirm loeschen
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=COLOR_BACKGROUND_NORMAL, fill=COLOR_BACKGROUND_NORMAL)
    # Datum/Uhrzeit auf jedem Screen
    now = datetime.now()
    date_time = now.strftime("%a; %d.%m.%y; %H:%M")
    draw.rectangle((0, 0, WIDTH, 14), outline=COLOR_BACKGROUND_CLOCK_BAR, fill=COLOR_BACKGROUND_CLOCK_BAR)
    draw.text(((WIDTH-draw.textlength(date_time, font=font))/2, 0), date_time,  font=font, fill=COLOR_TEXT_CLOCK_BAR)
    # ~ draw.line([(0, 14), (WIDTH, 14)], fill=(255, 255, 255))

    # entsprechenden Screen anzeigen
    if (temps["main_screen_idx"] == 0):
        # Stationsname und Logo
        y = 20
        for line in textwrap.wrap(stations[config['station_idx']]['name'], 15):
            draw.text(((WIDTH-draw.textlength(line, font=font_b))/2, y), line,  font=font_b, fill=COLOR_TEXT_NORMAL)
            y = y +15
        y = y + 5
        logo_img = load_webimage(stations[config['station_idx']]['favicon'], 90, HEIGHT-y, stations[config['station_idx']]['name'], PATH_LOGO_CACHE, DEFAULT_LOGO)
        img.paste(logo_img, (int((WIDTH-logo_img.width)/2), int(HEIGHT-logo_img.height)))
        
    elif (temps["main_screen_idx"] == 1):
        # Media-Infos aus Stream
        try:
            y = 20
            for line in textwrap.wrap(media.get_meta(Meta.NowPlaying), 18):
                draw.text((5, y), line, font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            y = y + 5
        except:
            pass
        try:
            for line in textwrap.wrap(media.get_meta(Meta.Title), 18):
                draw.text((5, y), line, font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            y = y + 5
        except:
            pass
        try:
            for line in textwrap.wrap(media.get_meta(Meta.Genre), 18):
                draw.text((5, y), line, font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
        except:
            pass

    elif (temps["main_screen_idx"] == 2):
        # Infos aus Stations-DB
        y = 20
        for line in textwrap.wrap(stations[config['station_idx']]['name'], 15):
            draw.text(((WIDTH-draw.textlength(line, font=font_b))/2, y), line,  font=font_b, fill=COLOR_TEXT_NORMAL)
            y = y + 15
        y = y + 5
        try:
            if len(stations[config['station_idx']]['country']) > 0:
                draw.text((5, y), stations[config['station_idx']]['country'][0:20],  font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            if len(stations[config['station_idx']]['state']) > 0:
                draw.text((5, y), stations[config['station_idx']]['state'][0:20],  font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            if len(stations[config['station_idx']]['language']) > 0:
                draw.text((5, y), stations[config['station_idx']]['language'][0:20],  font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            if len(stations[config['station_idx']]['codec']) > 0:
                draw.text((5, y), stations[config['station_idx']]['codec'],  font=font, fill=COLOR_TEXT_NORMAL)
                y = y + 15
            draw.text((5, y), F"{stations[config['station_idx']]['bitrate']}Kb/s",  font=font, fill=COLOR_TEXT_NORMAL)
        except:
            draw.text((5, y), "no database...",  font=font, fill=COLOR_TEXT_NORMAL)

    elif (temps["main_screen_idx"] == 3):
        # dies und das
        draw.text((15, 30), "techn. Zeugs...",  font=font, fill=(255, 255, 255))
        draw.text((15, 50), f"station_idx = {config['station_idx']}",  font=font, fill=COLOR_TEXT_NORMAL)
        draw.text((15, 65), f"temp_st_idx = {temps['station_list_idx']}",  font=font, fill=COLOR_TEXT_NORMAL)
        draw.text((15, 80), f"volume = {config['volume']}",  font=font, fill=COLOR_TEXT_NORMAL)
        draw.text((15, 95), f"main_screen = {temps['main_screen_idx']}",  font=font, fill=COLOR_TEXT_NORMAL)

    disp.display(img)

# ***********************************************************************************************
def tft_display_app_off(): 
    #Bildschirm loeschen
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=COLOR_BACKGROUND_NORMAL, fill=COLOR_BACKGROUND_NORMAL)
    # Datum/Uhrzeit anzeigen
    now = datetime.now()
    date = now.strftime("%a, %d.%m.%Y")
    draw.text(((WIDTH-draw.textlength(date, font=font))/2, 60), date,  font=font, fill=COLOR_TEXT_NORMAL)
    time = now.strftime("%H:%M")
    draw.text(((WIDTH-draw.textlength(time, font=font_20))/2, 80), time,  font=font_20, fill=COLOR_TEXT_NORMAL)
    disp.display(img)

# ***********************************************************************************************
def tft_display_volume(): 

    txt = F"Volume: {config['volume']}"
    txt_font = font
   
    dx_space = 5
    dy_space = 5
    dy_bar = 10
    
    x = dx_space
    y = dy_space + 50
    
    # Fenster mit Label
    draw.rectangle((x, y, WIDTH-x, y + 6*dy_space), outline=COLOR_FRAME_WINDOW, fill=COLOR_BACKGROUND_WINDOW)

    draw.rectangle((draw.textbbox((x+1, y-1), txt, font=txt_font, language="de-DE")), outline=COLOR_BACKGROUND_LABEL_WINDOW, fill=COLOR_BACKGROUND_LABEL_WINDOW)
    draw.text((x+1, y-1), txt,  font=txt_font, fill=COLOR_TEXT_LABEL_WINDOW)
    
    # ...auch hier sollte man noch kuerzen koennen!!!
    draw.rectangle((x+dx_space, y+3*dy_space, x+dx_space + ((WIDTH - (x+dx_space)) - (x+dx_space)) * config["volume"]/VOLUME_MAX, y+3*dy_space+dy_bar), outline=COLOR_VOLUME_BAR, fill=COLOR_VOLUME_BAR)

    disp.display(img)
    
# ***********************************************************************************************
def tft_display_stations(): 

    label_font = font

    dx_space = 5
    dy_space = 22
    
    max_str_len = 16

    # Fenster mit Label
    draw.rectangle((dx_space, dy_space, WIDTH-dx_space, HEIGHT-dy_space), outline=COLOR_FRAME_WINDOW, fill=COLOR_BACKGROUND_WINDOW)
    draw.rectangle((draw.textbbox((dx_space+1, dy_space-1), "Stations:", font=label_font, language="de-DE")), outline=COLOR_BACKGROUND_LABEL_WINDOW, fill=COLOR_BACKGROUND_LABEL_WINDOW)
    draw.text((dx_space+1, dy_space-1), "Stations:",  font=label_font, fill=COLOR_TEXT_LABEL_WINDOW)
    
    # welcher Bereich der Liste soll angezeigt wrden?
    if (temps["station_list_idx"] < temps["station_list_top"]) :
        temps["station_list_top"] = temps["station_list_idx"]
        temps["station_list_bottom"] = temps["station_list_top"] + STATION_LIST_MAX_COUNT
        
    if ((temps["station_list_idx"] + 1) > temps["station_list_bottom"]):
        temps["station_list_bottom"] = temps["station_list_idx"] + 1
        temps["station_list_top"] = temps["station_list_bottom"] - STATION_LIST_MAX_COUNT
        
    if temps["station_list_bottom"] > STATIONS_COUNT:
        temps["station_list_bottom"] = STATIONS_COUNT
    
    # Pfeil oben/unten anzeigen, wenn da noch was ist, was nicht angezeigt wird
    t = ""
    if temps["station_list_top"] > 0:
        t = f"{chr(8593)}"  # Pfeil hoch
    if temps["station_list_bottom"] < STATIONS_COUNT:
        t = f"{t}{chr(8595)}"  # Pfeil runter
    draw.text((WIDTH-dx_space - 4*dx_space, dy_space + 2), t, font=font, fill=COLOR_TEXT_NORMAL)

    # entsprechenden Ausschnitt der Stationsliste anzeigen
    x = 2*dx_space
    y = dy_space + 20
    for i in range(temps["station_list_top"], temps["station_list_bottom"]):
        # aktuelle (angewaehlte) Station hervorheben oder eben nicht
        if i == temps["station_list_idx"]:
            draw.rectangle((draw.textbbox((x, y), stations[i]["name"][0:max_str_len], font=font)), outline=COLOR_BACKGROUND_SELECTED_STATION, fill=COLOR_BACKGROUND_SELECTED_STATION)
            draw.text((x, y), stations[i]["name"][0:max_str_len],  font=font, fill=COLOR_TEXT_SELECTED_STATION)
        else:
            draw.text((x, y), stations[i]["name"][0:max_str_len],  font=font, fill=COLOR_TEXT_WINDOW)
        y = y + 15
    
    disp.display(img)

# ***********************************************************************************************
def reset_temp_station_idx():
    temps["station_list_idx"] = config["station_idx"]

# ***********************************************************************************************
# ***********************************************************************************************
# ***********************************************************************************************


# Signalhandler
signal.signal(signal.SIGINT,signal_handler)
# ~ signal.signal(signal.SIGKILL,signal_handler)
signal.signal(signal.SIGHUP,signal_handler)
signal.signal(signal.SIGQUIT,signal_handler)
# ~ signal.signal(signal.SIGSTOP,signal_handler)
signal.signal(signal.SIGTERM,signal_handler)
signal.signal(signal.SIGPWR,signal_handler)

# Initialisierung
settings_read()
encoder_setup()
player_setup()
tft_setup()
load_stations()

# Endlos-Loop
# ~ try:
while True :

    # Fenster Lautstaerke
    if cycle_must_run("display_volume"):
        tft_display_volume()
        cycle_stop("display_volume")
        cycle_start("display_main", time_ms() + TIMEOUT_CLOSE_WINDOW, True)
        continue

    # Fenster Stationsliste
    if cycle_must_run("display_stations"):
        temps["station_list"] = True
        tft_display_stations()
        cycle_stop("display_stations")
        cycle_start("reset_temp_station_idx", time_ms() + TIMEOUT_CLOSE_WINDOW, True)
        cycle_start("display_main", time_ms() + TIMEOUT_CLOSE_WINDOW, True)
        continue
        
    # temporaeren Stations-Index zuruecksetzen, weil Select-Button nicht gedrueckt wurde
    if cycle_must_run("reset_temp_station_idx"):
        reset_temp_station_idx()
        cycle_stop("reset_temp_station_idx")
        continue

    # Hauptbildschirm
    if cycle_must_run("display_main"):
        temps["station_list"] = False
        tft_display_main()
        cycle_start("display_main", time_ms() + seconds_to_next_minute()*1000, True)
        # Media-Info-Screen oeffters aktualisieren
        if (temps["main_screen_idx"] == 1) and (seconds_to_next_minute()*1000 > REFRESH_MEDIA_INFOS):
            cycle_start("display_main", time_ms() + REFRESH_MEDIA_INFOS, True)
        continue
    
    # Off-Bildschirm
    if cycle_must_run("display_app_off"):
        tft_display_app_off()
        cycle_start("display_app_off", time_ms() + seconds_to_next_minute()*1000, True)
        continue

    sleep(0.05)

# ~ except KeyboardInterrupt:
    # ~ settings_write()
    # ~ player_stop()
    # ~ GPIO.cleanup()
