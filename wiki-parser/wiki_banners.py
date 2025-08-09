import pywikibot
import mwparserfromhell
import wikitextparser as wtp
import jsons
import json
import os
import re
import sys
from tqdm import tqdm
from datetime import date
from iteration_utilities import unique_everseen
from wiki_banner_fixes import BANNER_NAME_CHANGE, CORRECT_DATES_JP, CORRECT_DATES_NA
from django.utils.text import slugify

# Define format of progress bar.
BAR_FORMAT_BANNERS = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

# NOTE: Halloween Trilogy missing Kiyohime in first table
# NOTE: FGO 2nd Anni JP missing lots of servants

# NOTE: Used by parse()
# Keywords that indicate link-style rateups after it.
LINK_MATCHES = (
    "Draw rates",
    "Summoning Rate",
    "increased draw rates",
    "Re-Run Summoning Campaign",
    "Rate Up Servant :",
    "special summoning pools",
    "Summon.*? Campaign.*?=", # Main Quest 1/2 AP + Shinjuku Summoning Campaign
    "Summon.*? Campaign 2=",
    "New Servant",
    "summoning campaign for",
    "Summon rates for the following",
    "rate-up event",
    "Commemoration Summoning Campaign",
    "Rate Up Schedule \(Female-Servants 2\)",
    "Rate Up \(Male-Servants\)",
    "Servant Lineups",
    "■ .*? Downloads Summoning Campaign",
)

# Keywords before a section of text that should be removed before link-style parsing is done.
REMOVE_MATCHES = (
    "receive one free",
    "==First Quest==",
    "==Prologue==",
    "==.*?Trial Quest.*?==",
    "Lucky Bag Summoning",
    "Music=",
    "Quest=",
    "Grand Summon",
    "Updates?\s?=",
    "New Information=",
    "New Servant Interlude",
)

# Pages that should not be parsed nor merged into.
# TODO: Rework this to automatically remove GSSRs when parsing titles
EXCLUDE_PAGES = (
    "2017 New Year Lucky Bag Summoning Campaign",
    "Fate/Grand Order Fes. 2017 ～2nd Anniversary～ Lucky Bag Summoning Campaign",
    "Fate/Grand Order Fes. 2018 ～3rd Anniversary～ Lucky Bag Summoning Campaign",
    "New Year Lucky-Bag Summoning Campaign 2019",
    "Fate/Grand Order Fes. 2019 ～4th Anniversary～/Lucky Bag Summoning Campaign",
    "New Year Lucky-Bag Summoning Campaign 2020",
    "Fate/Grand Order ～5th Anniversary～ Lucky Bag Summoning Campaign",
    "Lucky Bag 2021 Summoning Campaign New Year Special",
    "Fate/Grand Order ～6th Anniversary～ Lucky Bag Summoning Campaign",
    "Lucky Bag 2022 Summoning Campaign New Year Special",
    "Fate/Grand Order ～7th Anniversary～ Lucky Bag Summoning Campaign",
    "WinFes 2018/19 Commemoration Campaign: Kumamoto",
    "Fate/Apocrypha Event Pre-Release Campaign (US)/Rate Up Schedule",
    "Valentine 2020/Main Info",
    "Lucky Bag 2024 Summoning Campaign New Year Special",
    "Fate/Grand Order ～9th Anniversary～ Destiny Order Summoning Campaign",
    "Fate/Grand Order ～10th Anniversary～ Lucky Bag Summoning Campaign",
    "Fate/Grand Order ～10th Anniversary～ Destiny Order Summoning Campaign (Seven Classes)",
    "Fate/Grand Order ～10th Anniversary～ Destiny Order Summoning Campaign (Extra Classes)",
)

# The same rateup that shows up in two different events, need to skip 1 to prevent duping.
EXCLUDE_PAGES_WITH_PARENT = {
    'Archetype Inception Summoning Campaign' : 'Celeb Summer Experience!',
    'Grand Duel Extra Summoning Campaign' : 'Grand Duel Extra Pre-Release Campaign',
}

# Wiki pages with errors that prevent parsing that should be fixed.
PAGE_FIXES = {
    'Class Specific Summoning Campaign (US)' : [r'\|(.*)}}\n\[\[', r'|\1}}\n|}\n[['], # Class Specific Summoning Campaign (US)
    'FGO Summer 2018 Event Revival (US)/Summoning Campaign' : [r'{{Marie Antoinette}}', r'{{Marie Antoinette (Caster)}}'],
    'Class Based Summoning Campaign August 2021 (US)' : [r'Knight Classes=\n(.*\n)', r'Knight Classes=\n\1! colspan=2|Rate-Up Servant List'],
    'Class Based Summoning Campaign March 2023 (US)' : [r'</tabber>', r'|}\n</tabber>'],
    'Holy Grail Front ~Moonsault Operation~/Event Info' : [r'{{!}}', r'|'],
    'Servant Summer Festival! 2018 Rerun/Main Info' : [r'=\n*<center>\n*{\|\n*\|(\[\[.*)\n*\|}\n*<\/center>', r'=\n\1\n'],
    'Back to School Campaign 2024 (US)' : [r'</tabber>', r'|}\n</tabber>'],
}

# Keywords before a section of text that should be removed before any parsing is done.
PRIORITY_REMOVE_MATCHES = (
    "CBC 2022=",
    "{{Napoléon}} {{Valkyrie}} {{Thomas Edison}}", # WinFes 2018/19 Commemoration Summoning Campaign
    "Craft Essences are now unique per party, allowing Servants in multiple parties to hold different Craft Essences", # London Chapter Release
    r"==New \[\[Friend Point\]\] Gacha Servants==",
)

# Pages with wikitables that can generate false positives so table-style parsing should be skipped.
SKIP_TABLE_PARSE_PAGES = (
    "Prisma Codes Collaboration Event (US)/Summoning Campaign",
)

# Keywords that indicate the wikitable is a rateup servants wikitable.
TABLE_MATCHES = (
    "New Servant",
    "Rate-Up Servants",
    "Rate-Up Limited Servants",
    "Rate-Up Servant",
    "Rate Up Servant",
    "Rate-up Servants",
    "Rate-Up Schedule",
    "All-Time Rate Up",
    "Summoning Campaign Servant List", # Swimsuit + AoE NP Only Summoning Campaign
    "Featured Servants", # Interlude Campaign 14 and 16
    "Rate-Up", # New Year Campaign 2018
    "Limited Servant",
    "Limited Servants", # S I N Summoning Campaign 2
    "Edmond Dantès]] {{LimitedS}}\n|{{Avenger}}\n|-\n|4{{Star}}\n|{{Gilgamesh (Caster)", # Servant Summer Festival! 2018/Event Info
)

# Servant names that are incorrect on the wiki that should be fixed.
NAME_FIXES = {
    'Attila' : 'Altera', # FGO Summer Festival 2016 ~1st Anniversary~
    "EMIYA (Alter) NA" : "EMIYA (Alter)",
    "Jaguar Warrior" : "Jaguar Man",
    "Tlaloc" : "Tenochtitlan",
}

# Rateup servants that are missing from the banner on the wiki that should be fixed.
RATEUP_FIXES = {
    'S I N Chapter Release' : 'Jing Ke',
    'New Interludes + Class Pickup Summoning Campaign (US)' : 'Hōzōin Inshun',
}

# Pages with multiple rateups that should be merged into one regardless of whether there are common servants.
FORCE_MERGE = (
    "Fate/Apocrypha Collaboration Event Revival (US)/Summoning Campaign",
    "Chaldea Boys Collection 2023 (US)",
    "Chaldea Boys Collection 2024 (US)",
    "Valentine 2023 Event (US)/Summoning Campaign",
    "Class-Based Summoning Campaign (September 2019)",
    "Class-Based Summoning Campaign (March 2021)",
    "Class Based Summoning Campaign March 2023 (US)",
    "Class Based Summoning Campaign August 2021 (US)",
    "Singularity Summon Campaign September 2018 (US)",
    "Singularity Summon Campaign (US)",
    "Singularity Pickup Summon (US)",
)

# Specify specific rateups in summoning campaigns that should not be merged into any other rateups.
NO_MERGE = {
    "GUDAGUDA Close Call 2021/Event Info" : (1,),
    "Nanmei Yumihari Hakkenden/Summoning Campaign" : (1, 2,),
    "Nahui Mictlan Chapter Release Part 2" : (1,),
    "FGO THE STAGE Camelot Release Campaign (US)" : (2,),
    "Avalon le Fae Conclusion Campaign (US)" : (1, 2,),
    "GUDAGUDA Ryouma's Narrow Escape 2023 (US)/Summoning Campaign" : (1,),
    "Nanmei Yumihari Eight Dog Chronicles (US)/Summoning Campaign" : (1, 2, 3,),
    "FGO Festival 2024 ~7th Anniversary~ (US)/Summoning Campaign" : (1, 2,),
    "FGO Learning With Manga Collaboration Event (US)/Summoning Campaign" : (1, 2,),
    "GUDAGUDA New Yamataikoku 2024 (US)/Summoning Campaign": (1, 2,),
    "White Day 2025 Event (US)/Summoning Campaign": (1, 2),
    "Pilgrimage Festival Part 1 (US)/Summoning Campaign": (0, 1),
    "Illya's Karakuri Castle (US)/Summoning Campaign": (1, 2),
}

# Pages that should be link-style parsed regardless of keywords being present.
PRIORITY_PAGES = (
    "Amakusa Shirō Summoning Campaign",
    "Babylonia Summoning Campaign 2",
    "Salem Summoning Campaign 2",
    "Valentine 2017 Summoning Campaign Re-Run",
    "Anastasia Summoning Campaign 2",
    "Nero Festival Return ~Autumn 2018~ (US)/Summoning Campaign",
    "Prisma Codes Collaboration Event (US)/Summoning Campaign",
)

# Remove slash and everything after in the subpage title
SUBPAGE_TITLE_REMOVE = (
    "/Event Info",
    "/Event_Info",
    "/Main Info",
    "/Main_Info",
    "/Event Summary",
    "/Info",
)

# Replace slash with space in the subpage title
SUBPAGE_TITLE_REPLACE = (
    "/Summoning",
    "/Summon",
    "/FP",
    "/Merlin",
)

# Month name to number mapping
MONTHS = {
    "January" : 1, "Jan" : 1,
    "February" : 2, "Feb" : 2,
    "March" : 3, "Mar" : 3,
    "April" : 4, "Apr" : 4,
    "May" : 5,
    "June" : 6, "Jun" : 6,
    "July" : 7, "Jul" : 7,
    "August" : 8, "Aug" : 8,
    "September" : 9, "Sept" : 9,
    "October" : 10, "Oct" : 10,
    "November" : 11, "Nov" : 11,
    "December" : 12, "Dec" : 12,
}

# Do not parse dates
SKIP_DURATION_PARSE = (
    "SE.RA.PH",
)

# Only CE banners
FAKE_BANNERS = (
    "MELTY BLOOD: TYPE LUMINA Mashu's Game Entry Commemorative Campaign",
    "F/GO Memories III Release Commemoration Campaign",
    "F/GO Memories III Release Commemoration Summoning Campaign",
    "F/GO Memories II Release Commemoration Campaign",
    "F/GO Memories II Release Commemoration Campaign Summoning Campaign",
    "Fate/Grand Order VR feat. Mashu Release Commemoration Campaign",
    "FGO Craft Essence Recollection 2023 Campaign (US)",
    "FGO 5th Anniversary Countdown Campaign (US)",
    "FGO Craft Essence Recollection Campaign (US)",
    "Fate/Grand Order VR feat. Mash Kyrielight Release Campaign (US)",
)

# NOTE: Used by rec_check_subpages()
# Keyword indicating a subpage with a summoning campaign
SUMMON_SUBPAGE = (
    "Summoning Campaign",
    "Summoning_Campaign",
    "Pick Up",
    "/Event Info",
    "/Event_Info",
    "/Main Info",
    "/Main_Info",
    "/Event Summary",
    "/Info",
    "/Summoning",
    "/Summon",
    "Advance Campaign",
    "Special Campaign",
    "Pre-Release_Campaign",
    "Pre-Release Campaign",
    "Commemorative Campaign",
    "Comeback Campaign",
    "Countdown Campaign",
    "Pre-Anniversary Campaign",
)

# NOTE: Used by merge_events()
# Merge one event's banners into another event's banners
MERGE_EVENTS_JP = {
    "Strange Fake -Whispers of Dawn- Broadcast Commemoration Summoning Campaign" : "Strange Fake -Whispers of Dawn- Broadcast Commemoration Campaign",
    "Ordeal Call Pre-Release Campaign" : "Ordeal Call Release Campaign",
    "Chaldea Boys Collection 2021" : "Slapstick Museum",
    "Chaldea Boys Collection 2019" : "The Antiquated Spider Nostalgically Spins Its Thread",
    "WinFes 2018/19 Commemoration Summoning Campaign 2" : "WinFes 2018/19 Commemoration Campaign: Osaka",
    "FGO Arcade Collaboration Pre-Release Campaign" : "Lilim Harlot",
    "Nahui Mictlan Lostbelt Part II Pre-Release Campaign" : "Nahui Mictlan Chapter Release Part 2",
    "Fate/Grand Order ～7th Anniversary～ Countdown Campaign" : "Fate/Grand Order ～7th Anniversary～",
    "Avalon le Fae Lostbelt Pre-Release Campaign" : "Avalon le Fae Chapter Release",
    "Yuga Kshetra Pre-Release Campaign" : "Yuga Kshetra Chapter Release",
    "Götterdämmerung Lostbelt Pre-Release Campaign" : "Götterdämmerung Chapter Release",
    "Fate/Accel Zero Order (Pre-Event)" : "Fate/Accel Zero Order Event",
    "Summer 2021 Summoning Campaign Rerun" : "Arctic Summer World",
    "Valentine 2021 Summoning Campaign Rerun" : "Valentine 2022",
    "Valentine 2020 Summoning Campaign Re-Run" : "Valentine 2021",
    "CBC 2016 ~ 2019 Craft Essences Summoning Campaign" : "Aeaean Spring Breeze",
    "Lord El-Melloi II Case Files Collaboration Pre-campaign" : "Lady Reines Case Files",
    "Valentine 2018 Summoning Campaign Re-Run" : "Valentine 2019",
    "Valentine 2017 Summoning Campaign Re-Run" : "Valentine 2018",
    "Chaldea Boys Collection 2016 Re-Run" : "Chaldea Boys Collection 2017",
    "London Campaign 2" : "London Chapter Release",
    "Witch on the Holy Night Collaboration Pre-Release Campaign" : "Kumano Hot Springs Killer Case",
    "Fate/Grand Order Fes. 2025 ～10th Anniversary～ Countdown Campaign" : "Fate/Grand Order ～10th Anniversary～",
    "Grand Duel Extra Pre-Release Campaign" : "Grand Duel: Extra",
}

# Merge one event's banners into another event's banners
MERGE_EVENTS_NA = {
    "FGO 6th Anniversary Daily Summoning Campaign" : "FGO Festival 2023 ~6th Anniversary~",
    "My Super Camelot 2023 Pre-Release Campaign" : "Grail Front Event ~My Super Camelot 2023~",
    "Chaldea Boys Collection 2023 Summoning Campaign 2" : "White Day 2023 Event",
    "Chaldea Boys Collection 2023" : "White Day 2023 Event",
    "Valentine 2022 Summoning Campaign Revival" : "Valentine 2023 Event",
    "Lostbelt 5 Conclusion Summoning Campaign" : "Olympus Chapter Release",
    "Chaldea Boys Collection 2022" : "White Day 2022 Event",
    "Chaldea Boys Collection 2018 - 2021 CE Summoning Campaign" : "White Day 2022 Event",
    "Chaldea Boys Collection 2021" : "White Day 2021 Event",
    "Valentine 2020 Summoning Campaign Revival" : "Valentine 2021 Event",
    "Valentine 2019 Summoning Campaign Revival" : "Valentine 2020 Event",
    "Valentine 2023 Summoning Campaign Revival" : "Valentine 2024 Event",
    "Chaldea Boys Collection 2018 Revival" : "Chaldea Boys Collection 2019",
    "London Campaign 2" : "London Chapter Release",
    "Okeanos Campaign 2" : "Okeanos Chapter Release",
    "Chaldea Boys Collection 2024" : "White Day 2024 Event",
    "FGO Summer 2023 Revival Summoning Campaign" : "FGO Summer 2024 Event",
    "Halloween Revival 2024 Summoning Campaign" : "Halloween 2024 Event",
}

# NOTE: Used by fix_banner_names()
# Change all banners' names
BANNER_NAME_FIX = {
    r"\|-\|" : "",
    r"Summoning$" : "Summoning Campaign",
    r"Summoning 1$" : "Summoning Campaign 1",
    r"Summoning 2$" : "Summoning Campaign 2",
    r"(?<!Improvements Campaign )Part I Summoning Campaign" : "Summoning Campaign 1",
    r"(?<!Improvements Campaign )Part II Summoning Campaign" : "Summoning Campaign 2",
    r"Summoning Campaign I$" : "Summoning Campaign 1",
    r"Summoning Campaign II$" : "Summoning Campaign 2",
    r"Summoning Campaign III$" : "Summoning Campaign 3",
    r"Summoning Campaign IV$" : "Summoning Campaign 4",
    r"Summoning Campaign V$" : "Summoning Campaign 5",
    r"Summoning Campaign VI$" : "Summoning Campaign 6",
    r"Summoning Campaign VII$" : "Summoning Campaign 7",
    r"Summoning Campaign VIII$" : "Summoning Campaign 8",
    r"Summoning Campaign IX$" : "Summoning Campaign 9",
    r"Saint Quartz Summon$" : "Summoning Campaign",
    r"Saint Quartz Summon I$" : "Summoning Campaign 1",
    r"Saint Quartz Summon II$" : "Summoning Campaign 2",
    r"Summon Campaign" : "Summoning Campaign",
    r"Summoning Campaign Friend Point Summon" : "FP Summoning Campaign",
    r"Summoning Campaign Summoning Campaign" : "Summoning Campaign",
    r"Campaign Summoning Campaign" : "Summoning Campaign",
    r"Tales of Chaldean Heavy Industries" : "Chaldea Boys Collection 2023",
    r"White Day 2022" : "Chaldea Boys Collection 2022 / White Day 2022",
    r"<SKIP1>Grand Duel Saber Summoning Campaign" : "Artoria Pendragon (Lily) Friend Point Summoning Campaign",
}

# NOTE: Used by parse_event_lists()
# Skip parsing certain dates in event list (pre-2023)
SKIP_DATES = {
    "Event List/2016 Events": ["|August 22 ~ August 31"],
    "Event List/2017 Events": ["|August 17 ~ September 1", "|July 20 ~ July 29"],
    "Event List/2018 Events": ["|July 4 ~ July 13"],
    "Event List (US)/2017 Events": ["|July 13 ~ July 20"],
    "Event List (US)/2018 Events": ["|August 6 ~ August 14"],
    "Event List (US)/2019 Events": ["|August 5 ~ August 20", "|July 19 ~ July 28"],
    "Event List (US)/2020 Events": ["|July 23 ~ August 1"],
}

# Skip parsing certain iamge files in event list (pre-2023)
SKIP_IMAGE_FILE = {
    "Event List/2016 Events": ["Banner 100739874.png"],
    "Event List/2017 Events": ["DeathJailDateUpdate.png", "Summer 2016 re-run part2.png", "Extra CCC Event Banner Real.png"],
    "Event List/2018 Events": ["DeadHeatRerun2.png"],
    "Event List/2019 Events": ["Binny ishtar.png"],
    "Event List (US)/2017 Events": ["66666LikesPart2.png"],
    "Event List (US)/2018 Events": ["FGO2018BannerPart2US.png"],
    "Event List (US)/2019 Events": ["DeathJailBannerUS.png", "FGOSummer2018RevivalPart2US.png", "CCCEventTeaserBannerUS.png"],
    "Event List (US)/2020 Events": ["DeathJailRevivalUS.png"],
    "Event List (US)/2021 Events": ["BINY2021Banner2US.png"],
}

# Include certain subpages in an event
INCLUDE_SUBPAGES = {
    "FGO 2016 Summer Event" : ["FGO 2016 Summer Event/Event Details", "FGO 2016 Summer Event/Part II Event Details"],
    "SE.RA.PH" : ["Fate/EXTRA CCC×Fate/Grand Order"],
    "FGO 2016 Summer Event Re-Run" : ["FGO 2016 Summer Event Re-Run/Event Info"],
    "Setsubun 2018" : ["Setsubun 2018/Main Info"],
    "Dead Heat Summer Race! Re-run" : ["Dead Heat Summer Race! Re-run/Event Info"],
    "FGO Summer 2018 Event (US)" : ["FGO Summer 2018 Event (US)/Summoning Campaign"],
    "FGO Summer 2018 Event Revival (US)" : ["FGO Summer 2018 Event Revival (US)/Summoning Campaign"],
    "Servant Summer Festival! 2018 Rerun" : ["Servant Summer Festival! 2018 Rerun/Main Info"],
    "FGO Summer 2019 Event (US)" : ["FGO Summer 2019 Event (US)/Summoning Campaign"],
    "Halloween 2018 Event Revival (US)" : ["Halloween 2018 Event Revival (US)/Summoning Campaign"],
    "The Tale of Setsubun (US)" : ["The Tale of Setsubun (US)/Summoning Campaign"],
    "FGO Summer 2019 Event Revival (US)" : ["FGO Summer 2019 Event Revival (US)/Summoning Campaign"],
}

# Include pages that are missing from the event list
INCLUDE_PAGES = {
    "Anime NYC 2024 Campaign (US)" : (2024, "NA", "AnimeNYC2024CampaignUS.png", "Road to 7: Lostbelt No.4 Campaign (US)"),
}

# Keep certain events so it can have banners merged into it
ADD_EMPTY_ENTRY = (
    "Slapstick Museum",
    "The Antiquated Spider Nostalgically Spins Its Thread",
    "White Day 2023 Event (US)",
    "White Day 2022 Event (US)",
    "White Day 2021 Event (US)",
)

# List of JP event pages
EVENT_LIST_JP = (
    "Event List/2015 Events",
    "Event List/2016 Events",
    "Event List/2017 Events",
    "Event List/2018 Events",
    "Event List/2019 Events",
    "Event List/2020 Events",
    "Event List/2021 Events",
    "Event List/2022 Events",
    "Event List/2023 Events",
    "Event List/2024 Events",
    "Event List/2025 Events",
)

# List of NA event pages
EVENT_LIST_NA = (
    "Event List (US)/2017 Events",
    "Event List (US)/2018 Events",
    "Event List (US)/2019 Events",
    "Event List (US)/2020 Events",
    "Event List (US)/2021 Events",
    "Event List (US)/2022 Events",
    "Event List (US)/2023 Events",
    "Event List (US)/2024 Events",
    "Event List (US)/2025 Events",
)

class Event:
    def __init__(self, name, region, image_file, banners):
        self.name = name
        self.region = region
        self.image_file = image_file
        self.banners = banners
        self.slug = None
        self.start_date = None
        self.end_date = None
    
    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(str(self))
    
    def __eq__(self, other):
        return str(self) == str(other)
    
class Banner:
    def __init__(self, name, start_date, end_date, date_origin, rateups):
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.date_origin = date_origin
        self.rateups = rateups
        self.slug = None
    
    def copy_metadata(self, other):
        self.name = other.name
        self.start_date = other.start_date
        self.end_date = other.end_date
        self.date_origin = other.date_origin

SERVANT_DATA = None # Servant data
SERVANT_NAMES = None # Servant data
DIR_PATH = None # Path to the directory of this file
SITE = None # Wiki site
EVENT_SET_JP = {} # Dictionary of banners for JP
EVENT_SET_NA = {} # Dictionary of banners for NA
PAGES_VISITED = set() # Set of pages visited
CURRENT_YEAR = 0 # Current year
CURRENT_REGION = "" # Current region
PRESENT_YEAR = 2025

def banner_init():
    global SERVANT_DATA
    global SERVANT_NAMES
    global DIR_PATH
    global SITE

    DIR_PATH = os.path.dirname(__file__) # Path to the directory of this file
    SITE = pywikibot.Site() # Wiki site

    # Import the servant data.
    with open(os.path.join(DIR_PATH, 'servant_details.json')) as f:
        SERVANT_DATA = jsons.loads(f.read())

    # Get the names and IDs of all the servants.
    SERVANT_NAMES = {servant['name'] : int(servant['id']) for servant in SERVANT_DATA}

# Parse the raw date range strings into date objects
def date_parser(start_date, end_date, year):
    # Parse the month and year from the date strings
    start_mon_yr = start_date.split(",")[0].strip().split(" ")
    end_mon_yr = end_date.split(",")[0].strip().split(" ")

    # Parse the month and day from the start date string
    start_month = MONTHS[start_mon_yr[0]]
    start_day = int(re.sub(r'\D+', '', start_mon_yr[1]))

    # Parse the month and day from the end date string
    try:
        end_month = MONTHS[end_mon_yr[0]]
        end_day = int(re.sub(r'\D+', '', end_mon_yr[1]))
    # If the end date is missing, use the start date
    except KeyError:
        end_month = start_month
        end_day = start_day

    # Find the start and end years. Increment the end year if the duration is December-January
    start_year = year
    end_year = year if end_month >= start_month else year + 1
    
    # Overwrite the year if it is explicitly stated in the date string
    try:
        if len(start_mon_yr) > 2 and int(start_mon_yr[2]) > 2000 and int(start_mon_yr[2]) < 2100:
            start_year = int(start_mon_yr[2])
    except ValueError:
        pass
    try:
        if len(end_mon_yr) > 2 and int(end_mon_yr[2]) > 2000 and int(end_mon_yr[2]) < 2100:
            end_year = int(end_mon_yr[2])
    except ValueError:
        pass

    # Return the date range
    return (date(start_year, start_month, start_day), date(end_year, end_month, end_day))

# Split date strings into start and end dates
def date_splitter(date_str):
    date_split = date_str.split("~")
    if len(date_split) == 1:
        date_split = date_split[0].split("-")
    if len(date_split) == 1:
        date_split = date_split[0].split("～")
    
    return date_split

def get_header_info(page):
    text = page.text
    wikicode = mwparserfromhell.parse(text)
    templates = wikicode.filter_templates()
    header_idx = None

    # Check template 1 or 2 for the header
    if len(templates) > 0:
        if (templates[0].name.strip() == "EventHeaderJP" or templates[0].name.strip() == "EventHeaderNA"):
            header_idx = 0
        if (templates[1].name.strip() == "EventHeaderJP" or templates[1].name.strip() == "EventHeaderNA"):
            header_idx = 1
        
    if header_idx is not None:
        # Get the image file
        image_file = templates[header_idx].get("image").value.strip()

        # Get the raw start date
        start_date_str = templates[header_idx].get("start").value.strip()

        # Get the raw end date
        try:
            end_date_str = templates[header_idx].get("end").value.strip()
        # If the end date is missing or invalid, set the end date to the start date
        except ValueError:
            end_date_str = start_date_str
        if not end_date_str:
            end_date_str = start_date_str

        # Parse the start and end date into date objects
        duration = date_parser(start_date_str, end_date_str, CURRENT_YEAR)
        return (image_file, duration)
    else:
        # Throw an assert
        assert False, f"Error: No EventHeaderJP or EventHeaderNA template found in page {page.title()}"

# Parse an FGO wiki page
def parse(event_set, page, duration, parent=None, image_file=None):
    # Finds indexes of matching keywords in order to breaks link-style pages into chunks, each with a rateup.
    def create_text_splits(text):
        splits = {}

        # Find index of keywords that indicate a rateup coming after.
        for string in LINK_MATCHES:
            matches = re.finditer(string, text)
            # Mark it to be preserved.
            for match in matches:
                splits[match.start()] = True
        
        # Find index of keywords that are before sections causing false positives.
        for string in REMOVE_MATCHES:
            matches = re.finditer(string, text)
            # Mark it to be removed.
            for match in matches:
                splits[match.start()] = False
        
        # Sort the indexes of the splits and return it.
        splits = {k: v for k, v in sorted(splits.items(), key=lambda item: item[0], reverse=True)}
        return splits

    # Fix any errors in the servant name.
    def correct_name(name):
        if name in NAME_FIXES:
            return NAME_FIXES[name]
        return name

    def parse_wikilinks(links):
        # Initialize the list of rateup servants.
        rateup_servants = {}

        # Check every link to see if it is a valid servant name.
        for link in links:
            # Fix any errors in the servant name
            name = correct_name(str(link.title).strip())
            # Add the servant name and ID to the dictionary of rateup servants if it is a valid servant name.
            if name in SERVANT_NAMES:
                rateup_servants[SERVANT_NAMES[name]] = name

        # If rateup servants were found...
        if rateup_servants:
            # Sort and dedupe the servants.
            return dict(sorted(rateup_servants.items()))

    # Get the title of the page
    title = page.title()
    PAGES_VISITED.add(title)

    # Do not parse explicitly excluded pages and user blogs.
    if title in EXCLUDE_PAGES or (title in EXCLUDE_PAGES_WITH_PARENT and parent == EXCLUDE_PAGES_WITH_PARENT[title]) or title.startswith("User blog:"):
        return

    # Get contents of the page and remove HTML comments
    text = re.sub(r'<!--(.|\n)*?-->', '', page.text)

    # Apply any explicitly defined fixes
    if title in PAGE_FIXES:
        text = re.sub(PAGE_FIXES[title][0], PAGE_FIXES[title][1], text)

    # Find and apply any priority text removals
    for string in PRIORITY_REMOVE_MATCHES:
        matches = re.finditer(string, text)
        # Remove the match and everything after it
        for match in matches:
            text = text[:match.start()]

    # Parse the page contents
    wikicode = mwparserfromhell.parse(text)

    # Initialize the list of rateups
    rateups = []

    # Find and parse the rateup servants wikitable, unless the page is explicitly marked to skip this
    if title not in SKIP_TABLE_PARSE_PAGES:
        # Get all the tags in the page, any of which may contain the rateup servants wikitable.
        tags = wikicode.filter_tags()

        num_parsed = 0
        # Find any tags containing the rateup servants wikitable
        for i, tag in enumerate(tags):
            # For the tag to contain a valid rateup servants wikitable:
            # 1. The tag must have a "class" field.
            try:
                class_type = tag.get("class").value.strip()
            except ValueError:
                class_type = None

            # 2. The "class" field must contain "wikitable".
            # 3. The tag must contain at least one keyword indicating that it is a rateup servants wikitable.
            has_valid_class = class_type == 'wikitable' or class_type == 'fandom-table'
            has_valid_keyword = any([x in tag for x in TABLE_MATCHES])
            if not has_valid_class or not has_valid_keyword:
                continue

            # Parse the tag
            table = mwparserfromhell.parse(tag)

            # Get all the templates in the tag.
            # Example: "{{wikipage}}""
            templates = table.filter_templates()

            # Initialize the list of rateup servants.
            rateup_servants = {}

            # Get the rateup servants from the templates
            # Example: "{{servant_name}}"
            for template in templates:
                # Fix any errors in the servant name
                name = correct_name(str(template.name))

                # Add the servant name and ID to the dictionary of rateup servants if it is a valid servant name, with ID as the key
                if name in SERVANT_NAMES:
                    rateup_servants[SERVANT_NAMES[name]] = name
            
            # Manually add any rateup servants that are incorrectly left out of the table on the wiki
            if title in RATEUP_FIXES:
                rateup_servants[SERVANT_NAMES[RATEUP_FIXES[title]]] = RATEUP_FIXES[title]

            # If rateup servants were found in the wikitables...
            if rateup_servants:
                # Sort the servants by ID.
                rateup_servants = dict(sorted(rateup_servants.items()))
                # Append to the list of rateups.
                rateups.append(rateup_servants)

                # If the rateup that was just added and the previous rateup have any servants in common, merge the new one into the previous one.
                # Also, merge any rateups that are forced to be merged.
                # Don't merge if the whole page is marked not to be merged or a specific rateup is marked not to be merged.
                if len(rateups) > 1 \
                    and (title in FORCE_MERGE \
                         or (len(set(rateups[-2].keys()).intersection(set(rateups[-1].keys()))) > 0 \
                             and not (title in NO_MERGE and num_parsed in NO_MERGE[title]))):
                    # Merge the new banner into the previous one.
                    rateups[-2].update(rateups[-1])
                    # Sort the servants by ID.
                    rateups[-2] = dict(sorted(rateups[-2].items()))
                    # Remove the new banner since it's been merged into the previous one.
                    del rateups[-1]

                    # Check if the newly merged banner can be merged again to the new previous banner
                    # Don't do this second merge if explicitly marked not to
                    if len(rateups) > 1 \
                        and len(set(rateups[-2].keys()).intersection(set(rateups[-1].keys()))) > 0 \
                        and title not in NO_MERGE:
                        # Merge the new banner into the previous one.
                        rateups[-2].update(rateups[-1])
                        # Sort the servants by ID.
                        rateups[-2] = dict(sorted(rateups[-2].items()))
                        # Remove the new banner since it's been merged into the previous one
                        del rateups[-1]

                # Keep track of the number of rateup tables that have been parsed.
                num_parsed += 1

    # In older pages, the rateup servants are not in a wikitable, but are instead in links.
    # Only parse wikilinks if the wikitable parsing did not find any rateups.
    # Stop parsing wikilinks after 2021 and onwards if the region is JP and 2023 and onwards if the region is NA.
    if not (CURRENT_REGION == "JP" and CURRENT_YEAR >= 2021) and not (CURRENT_REGION == "NA" and CURRENT_YEAR >= 2023):
        # If the page is marked as priority, no need to look for keywords and parse servants regardless.
        if not rateups and title in PRIORITY_PAGES:
            # Get all the links in the page.
            links = wikicode.filter_wikilinks()

            # Find rateup servants.
            rateup_servants = parse_wikilinks(links)
            # If rateup servants were found...
            if rateup_servants:
                # Sort the servants by ID.
                rateup_servants = dict(sorted(rateup_servants.items()))
                # Append the rateup to the start of the rateups list.
                rateups.insert(0, rateup_servants)

        # If the page is not marked as priority, look for keywords and parse servants if found.
        elif not rateups and title not in PRIORITY_PAGES:
            links = []
            # Get the indexes that indicate sections of the text to parse and sections to skip.
            splits = create_text_splits(text)
            
            # Base text will hold the remaining part of the page that hasn't been parsed yet.
            base_text = text
            # Go through each index from the bottom of the page to the top.
            for key, value in splits.items():
                # Parse (or skip) the text between the current index and the remaining part of the page.
                parse_text = base_text[key:]
                # Save the remaining part of the page that hasn't been parsed yet for the next iteration.
                base_text = base_text[:key]
                # If the section is marked to be removed, skip it.
                if not value:
                    continue
                # Parse the section.
                sub_wikicode = mwparserfromhell.parse(parse_text)
                # Get all the links in the section.
                links = sub_wikicode.filter_wikilinks()

                # Find rateup servants.
                rateup_servants = parse_wikilinks(links)
                # If rateup servants were found...
                if rateup_servants:
                    # Sort the servants by ID.
                    rateup_servants = dict(sorted(rateup_servants.items()))
                    # Append the rateup to the start of the rateups list (since the page is parsed backwards).
                    rateups.insert(0, rateup_servants)

    # Dedupe the rateups.
    rateups = list(unique_everseen(rateups))

    # Set the banner title initially to the event title
    subpage_title = title
    # Remove any post-slash subpage names that don't have "Summon" in their name
    if any(keyword in title for keyword in SUBPAGE_TITLE_REMOVE):
        subpage_title = re.sub(r'(?<!Fate)\/.*', '', title)
    # Replace the slash with a space if the subpage name has "Summon" in it
    elif any(keyword in title for keyword in SUBPAGE_TITLE_REPLACE):
        subpage_title = re.sub(r'(?<!Fate)\/', ' ', title)
    
    # Create a list of banner titles
    rateup_titles = [subpage_title] * len(rateups)

    # Default date origin
    date_origin = "event list"

    # Parse dates from pages with new-style event headers
    templates = wikicode.filter_templates()
    if len(templates) > 0 and (templates[0].name.strip() == "EventHeaderJP" or templates[0].name.strip() == "EventHeaderNA"):
        # Get the raw start date
        start_date_str = templates[0].get("start").value.strip()

        # Get the raw end date
        try:
            end_date_str = templates[0].get("end").value.strip()
        # If the end date is missing or invalid, set the end date to the start date
        except ValueError:
            end_date_str = start_date_str
        if not end_date_str:
            end_date_str = start_date_str

        # Parse the start and end date into date objects
        duration = date_parser(start_date_str, end_date_str, CURRENT_YEAR)
        date_origin = "event header jp new" if templates[0].name.strip() == "EventHeaderJP" else "event header na new"
    # Parse dates from pages with old-style event headers
    else:
        # Get the lines from the page
        lines = text.splitlines()

        # Check each line for the duration
        for i, line in enumerate(lines):
            # Only check the first 4 lines
            if i >= 4:
                break
            # If the line contains "Duration" and is not marked to skip, parse the date
            if "Duration" in line and title not in SKIP_DURATION_PARSE:
                # Remove the bolding tags from the line
                line = re.sub(r"'''", '', line)

                # Attempt to split the start and end date using either ~, -, or ～
                date_split = date_splitter(line.split(": ")[1])

                # If the end date is missing or invalid, set the end date to the start date
                if not date_split[1].strip():
                    date_split[1] = date_split[0]
                
                # Parse the start and end date into date objects
                duration = date_parser(date_split[0], date_split[1], CURRENT_YEAR)
                date_origin = "event header jp old"
                break

    # Create a list of dates the same size as the list of rateups.
    dates = [duration] * len(rateups)
    date_origins = [date_origin] * len(rateups)

    # Finds dates and banner titles on pages with multiple summoning campaigns on different tabs
    matches = re.findall(r'(.*Summo.*(?:\w|\)))=\n*((?:\[\[|{{|{\|).*)\n\n*(?:.*Duration.*?(?: |\'|:)([A-Z].*))?', text)

    # Check every found summoning campaign tab
    i = 0
    for match in matches:
        # Cut out GSSR tabs, CE-only banners, and parent tabs of summoning campaign tabs
        if "Lucky" not in match[0] and "Guaranteed" not in match[0] and title not in FAKE_BANNERS and "tabber" not in match[1]:
            # Update the banner title by merging the original banner title with the tab text if possible.
            try:
                rateup_titles[i] = f'{subpage_title} {match[0].strip()}'
            except:
                pass

            # Update the duration if a new duration was found
            if match[2]:
                date_split = date_splitter(match[2])
                dates[i] = date_parser(date_split[0], date_split[1], CURRENT_YEAR)
                date_origins[i] = "tab"

            # Increment the banner index
            i += 1
    
    # Create banner objects for each rateup.
    banners = [Banner(rateup_titles[i], dates[i][0], dates[i][1], date_origins[i], rateups[i]) for i in range(len(rateups))]

    # Check if the event is a subsequent Summoning Campaign that can be merged into a Chapter Release event
    chapter_release_title = f'{title.split("Summoning Campaign")[0].strip()} Chapter Release'
    if chapter_release_title in event_set or chapter_release_title + " (US)" in event_set:
        if chapter_release_title + " (US)" in event_set:
            chapter_release_title += " (US)"
        # Get the rateups of the chapter release
        chapter_release_rateups = [banner.rateups for banner in event_set[chapter_release_title].banners]

        # Check if each rateup list is already in the Chapter Release event
        for src_i, rateup in enumerate(rateups):
            # If the rateup is already in the Chapter Release event...
            if rateup in chapter_release_rateups:
                # Get the index of the rateup in the Chapter Release event
                dest_i = chapter_release_rateups.index(rateup)

                # Transfer date duration and rateup title over
                temp_banner = Banner(rateup_titles[src_i], dates[src_i][0], dates[src_i][1], date_origins[src_i], None)
                event_set[chapter_release_title].banners[dest_i].copy_metadata(temp_banner)
            # If the rateup list is not already in the Chapter Release event, add it
            else:
                event_set[chapter_release_title].banners.append(banners[src_i])
    # If the banner already has a predetermined parent, add it to that parent
    elif parent:
        # If the parent event already exists, add the banners to it
        try:
            event_set[parent].banners.extend(banners)
        # If the parent event does not exist, create it
        except KeyError:
            new_event = Event(parent, CURRENT_REGION, image_file, banners)
            event_set[new_event] = new_event
    # If the event is not in the set, add it
    else:
        new_event = Event(title, CURRENT_REGION, image_file, banners)
        event_set[new_event] = new_event

# Delete any pre-release events with rateups that are already in the main event
def pre_release_remove(event_set):
    # Get the list of events
    events = list(event_set.values())
    keys = list(event_set.keys())
    try:
        # Check the last 3 events before the one just added
        for i in range(-2, -5, -1):
            mark_for_del = False

            # Get the list of rateups for the event being checked
            prev_event_rateups = [banner.rateups for banner in events[i].banners]
            # Check if any of the rateups are in the recently parsed event
            for rateup in prev_event_rateups:
                # Get the list of rateups for the recently parsed event
                recent_event_rateups = [banner.rateups for banner in events[-1].banners]
                # If the rateup is in the recently parsed event, copy the name and date over and delete it later
                if rateup in recent_event_rateups:
                    # Get the source and destination indexes of the rateup
                    dest_i = recent_event_rateups.index(rateup)
                    src_i = prev_event_rateups.index(rateup)
                    # Copy the name and date over
                    events[-1].banners[dest_i].copy_metadata(events[i].banners[src_i])
                    # Mark the event for deletion
                    mark_for_del = True
            # Delete the checked redundant event
            if mark_for_del == True:
                del event_set[keys[i]]
    # Skip if there are less than 3 events
    except IndexError:
        pass

# Delete any subsequent summoning campaigns that are already in the main event
def post_release_remove(event_set):
    # Get the list of events
    events = list(event_set.values())
    try:
        mark_for_del = False
        # Check the last 3 events before the one just added
        for i in range(-2, -5, -1):
            # Get the list of rateups for the recently parsed event
            recent_event_rateups = [banner.rateups for banner in events[-1].banners]
            # Check if any of the rateups are in the event being checked
            for rateup in recent_event_rateups:
                # Get the list of rateups for the event being checked
                prev_event_rateups = [banner.rateups for banner in events[i].banners]
                # If the rateup is in the event being checked, copy the name and date over and delete it later
                if rateup in prev_event_rateups:
                    # Get the source and destination indexes of the rateup
                    dest_i = prev_event_rateups.index(rateup)
                    src_i = recent_event_rateups.index(rateup)
                    # Copy the name and date over
                    events[i].banners[dest_i].copy_metadata(events[-1].banners[src_i])
                    # Mark the event for deletion
                    mark_for_del = True
    # Skip if there are less than 3 events
    except IndexError:
        pass
    # Delete the recently parsed redundant event
    if mark_for_del == True:
        del event_set[list(event_set.keys())[-1]]

# Merge any pre-release events not already in the main event
def pre_release_merge(event_set):
    # Delete any existing precampaigns
    events = list(event_set.values())
    keys = list(event_set.keys())
    try:
        for i in range(-2, -5, -1):
            # Find the name of the event the pre-release is for
            pre_release_parent = events[i].name.split("Pre-Release")[0].strip()
            # If that event is the same as the most recent event, merge the pre-release into the main event
            if pre_release_parent == events[-1].name or pre_release_parent + " (US)" == events[-1].name:
                # Merge the pre-release banners into the main event
                events[-1].banners.extend(events[i].banners)
                # Delete the pre-release event
                del event_set[keys[i]]
    # Skip if there are less than 3 events
    except IndexError:
        pass

# Parse event start and end dates from banners
def create_event_dates(event_set):
    # For each event in the event set...
    for event in (pbar := tqdm(event_set.values(), bar_format=BAR_FORMAT_BANNERS)):
        pbar.set_postfix_str(event)

        # Set the start and end dates of the event
        start_dates = []
        end_dates = []
        for banner in event.banners:
            start_dates.append(banner.start_date)
            end_dates.append(banner.end_date)
        event_set[event].start_date = min(start_dates)
        event_set[event].end_date = max(end_dates)

# Recursively check for summoning campaign subpages
def rec_check_subpages(event_set, event_page, date, parent_title):
    # Get the contents of the event page
    event_text = event_page.text
    # Parse the event page
    event_wikicode = mwparserfromhell.parse(event_text)

    # Get the templates in the event page
    event_templates = event_wikicode.filter_templates()
    # For each template in the event page...
    for event_template in event_templates:
        # Get the name of the subpage
        event_subpage = str(event_template.name)
        # If the subpage name contains any of the keywords indicating a summoning campaign subpage...
        if any(keyword in event_subpage for keyword in SUMMON_SUBPAGE):
            # Get the name of the summoning campaign page (get rid of the ':')
            summon_name = event_subpage[1:]
            # Open the summoning campaign page
            summon_page = pywikibot.Page(SITE, summon_name)
            # Parse the summoning campaign page for rateups
            parse(event_set, summon_page, date, parent=parent_title)

            # Check another level of subpages
            rec_check_subpages(event_set, summon_page, date, parent_title)
            # Remove any pre-release events with rateups that are already in the main event
            pre_release_remove(event_set)

# Parse events
def parse_event_lists(event_lists, region):
    global CURRENT_YEAR
    global CURRENT_REGION

    # Parse event lists
    for event_list in event_lists:
        # Get the current year and region of the event list
        CURRENT_YEAR = int(event_list.split('/')[1][:4])
        CURRENT_REGION = region

        # Choose which event set to put the events into
        event_set = EVENT_SET_NA if CURRENT_REGION == "NA" else EVENT_SET_JP

        # Open the event list page
        page = pywikibot.Page(SITE, event_list)
        print(f"Parsing {page.title()}...")

        # Get the contents of the event list page
        text = page.text

        # Parse the event list page
        wikicode = mwparserfromhell.parse(text)
        # Get the date of each event
        date_list = []
        # Get a list of events
        events = None
        # Pre-2023 event lists uses wikilinks
        if CURRENT_YEAR < 2023:
            # Search through the page for the dates
            for line in text.splitlines():
                # If the line contains a month, save it.
                # Skip tabs, 2nd dates of events with 2 dates, and image links
                if any(month in line for month in MONTHS) \
                    and not line.endswith("=") \
                    and not (page.title() in SKIP_DATES and line in SKIP_DATES[page.title()]) \
                    and not "[[" in line:
                    # Remove the bar at the beginning of the line
                    line = re.sub(r'.*\|', '', line)
                    # Separate the raw date string into start and end date strings
                    date_split = date_splitter(line)
                    # Set the end date to the start date if the end date is missing, otherwise parse both dates into date objects
                    date_list.append(date_parser(line, line, CURRENT_YEAR) if len(date_split) == 1 \
                                     else date_parser(date_split[0], date_split[1], CURRENT_YEAR))
                    
            # Find all image links
            images = re.findall(r'\[\[File:(.*?)\|', text)
            if event_list in SKIP_IMAGE_FILE:
                for skip_image in SKIP_IMAGE_FILE[event_list]:
                    images.remove(skip_image)
                    
            # Get all the wikilinks in the page
            events = wikicode.filter_wikilinks()
            # Filter out non-event pages
            events = [x for x in events if not x.startswith("[[File:") and not x.startswith("[[Category:") and not x.startswith("[[#")]
            # Get the title of each event
            events = [str(x.title) for x in events]
        # 2023 and post-2023 event lists uses templates
        else:
            # Get all the templates in the page
            event_templates = wikicode.filter_templates()
            # Get the title of each event
            events = [x.get("event").value.strip() for x in event_templates]
            # Get the start date string of each event
            starts = [x.get("start").value.strip() for x in event_templates]
            # Get the image file name of each event
            images = [x.get("image").value.strip() for x in event_templates]

            # Get the end date string of each event
            ends = []
            for i, event_template in enumerate(event_templates):
                try:
                    ends.append(event_template.get("end").value.strip())
                # If the end date is missing, set the end date to the start date
                except ValueError:
                    ends.append(starts[i])
            
            # Parse the start and end date strings into date objects
            date_list = [date_parser(starts[i], ends[i], CURRENT_YEAR) for i in range(len(starts))]

        if len(events) != len(date_list):
            print(f"Error: Number of events ({len(events)}) does not match number of dates ({len(date_list)})")
            sys.exit(1)
        if len(events) != len(images):
            print(f"Error: Number of events ({len(events)}) does not match number of images ({len(images)})")
            sys.exit(1)

        # Reverse events and date list since events in the event list are listed from newest to oldest
        events.reverse()
        date_list.reverse()
        images.reverse()

        if CURRENT_YEAR == PRESENT_YEAR:
            current_event_category = pywikibot.Category(SITE, "Current Event" if CURRENT_REGION == "JP" else "Current Event (US)")
            current_events = []
            for page in current_event_category.articles():
                title = page.title()
                # If title in PAGES_VISITED, skip it
                if title in PAGES_VISITED or title in events:
                    continue
                image_file, duration = get_header_info(page)
                current_events.append((title, duration, image_file))
                # Sort current events by starting date in duration
                current_events.sort(key=lambda x: (x[1][0], x[1][1]))
            for event in current_events:
                events.append(event[0])
                date_list.append(event[1])
                images.append(event[2])

        # Add in pages that were missing from the event list.
        for include_event, include_event_data in INCLUDE_PAGES.items():
            include_year, include_region, include_image_file, insert_after = include_event_data
            # If the year matches the current year, add the event to the list
            if include_year == CURRENT_YEAR and include_region == CURRENT_REGION:
                # Insert after the event specified in the tuple
                i = events.index(insert_after) + 1
                events.insert(i, include_event)
                # Insert none for date
                date_list.insert(i, None)
                images.insert(i, include_image_file)

        # Create a dict where the key is the event name and the value is the date of the event.
        event_dates = dict(zip(events, date_list))
        event_images = dict(zip(events, images))

        # Parse each event
        for event in (pbar := tqdm(events, bar_format=BAR_FORMAT_BANNERS)):
            pbar.set_postfix_str(event)

            # Open the event page
            event_page = pywikibot.Page(SITE, event)
            # Parse the event page
            parse(event_set, event_page, event_dates[event], image_file=event_images[event])

            # Parse any explicitly defined subpages of the event page
            if event_page.title() in INCLUDE_SUBPAGES:
                for subpage in INCLUDE_SUBPAGES[event_page.title()]:
                    # Open the subpage
                    summon_page = pywikibot.Page(SITE, subpage)
                    # Parse the subpage and set the parent to the event page
                    parse(event_set, summon_page, event_dates[event], parent=event_page.title())
                    # Remove any pre-release events with rateups that are already in the main event
                    pre_release_remove(event_set)

            # Recursively find any summoning campaign subpages
            if event not in ADD_EMPTY_ENTRY:
                rec_check_subpages(event_set, event_page, event_dates[event], event_page.title())

            # Remove the recently parsed event if it has already been parsed as a subpage
            post_release_remove(event_set)
            # Merge any pre-release events not already in the main event
            pre_release_merge(event_set)

# Remove events with no banners.
def remove_empty(event_set):
    # Check each event for empty banners.
    for event in list(event_set):
        # If the banner list is empty, delete the event.
        if not event.banners:
            del event_set[event]

# Fix events with multiple summoning campaigns but the first one is missing a number.
def fix_banner_names(event_set):
    # Check each event to apply fixes to banner names
    for event in event_set:
        # Get the list of banner titles.
        banner_titles = [banner.name for banner in event_set[event].banners]
        # If multiple banners have the same name and only one needs to be renamed.
        skipped_dict = {}
        # Check each banner title
        for i, banner_title in enumerate(banner_titles):
            # Apply any explicitly defined fixes
            for original, replace in BANNER_NAME_FIX.items():
                # If the original string has "<SKIP#>string_to_replace" in it
                if "<SKIP" in original:
                    # Get the string_to_replace which is after the "<SKIP#>" part
                    skip_key = original[5:].split(">")[1]
                    skip_num = int(original[5:].split(">")[0])

                    # If the skip_key is not in the skipped_dict, initialize its count
                    if skip_key not in skipped_dict:
                        skipped_dict[skip_key] = 1
                        continue
                    # Increment the counter if it hasn't reached skip_num
                    elif skipped_dict[skip_key] < skip_num:
                        skipped_dict[skip_key] += 1
                        continue
                    # If the skip_num has been reached, replace the string
                    substituted = re.sub(skip_key, replace, banner_title)
                else:
                    # Replace it normally if string is present
                    substituted = re.sub(original, replace, banner_title)
                
                if substituted != banner_title:
                    event_set[event].banners[i].name = substituted
                    banner_title = substituted

    # Check each event for banners with missing numbers.
    for event in event_set:
        # Get the list of banner titles.
        banner_titles = [banner.name for banner in event_set[event].banners]

        # Check each banner title for "Campaign" without "Summoning Campaign" and missing numbers 
        for i, banner_title in enumerate(banner_titles):
            # If the banner title ends with "Campaign" but not "Summoning Campaign"...
            if banner_title.endswith("Campaign") and not banner_title.endswith("Summoning Campaign"):
                # Add "Summoning " behind "Campaign".
                event_set[event].banners[i].name = re.sub(r'Campaign$', 'Summoning Campaign', banner_title)

        # Get the list of banner titles.
        banner_titles = [banner.name for banner in event_set[event].banners]

        # Check each banner title for "Campaign" without "Summoning Campaign" and missing numbers 
        for i, banner_title in enumerate(banner_titles):
            # If the banner title ends with "Summoning Campaign 1" but there's no "Summoning Campaign 2" after it...
            if "Summoning Campaign 1" in banner_title:
                # Check the ones after it
                second_summon_found = False
                for j in range(i+1, len(banner_titles)):
                    # If a second campaign is found, don't remove the 1
                    if "Summoning Campaign 2" in banner_titles[j]:
                        second_summon_found = True
                        break
                # Otherwise, remove the 1
                if not second_summon_found:
                    event_set[event].banners[i].name = re.sub(r'Summoning Campaign 1', 'Summoning Campaign', banner_title)

            # If there is a second banner...
            if "Summoning Campaign 2" in banner_title:
                # Check the ones before it
                for j in range(max(i-1, 0), -1, -1):
                    # If it is missing a number, add the number to the end of it.
                    if banner_titles[j].endswith("Summoning Campaign")\
                        and banner_titles[j].split("Summoning Campaign")[0].strip() == banner_title.split("Summoning Campaign")[0].strip():
                        # Add a '1' to the end of the banner name
                        event_set[event].banners[j].name += " 1"
                        banner_titles[j] = event_set[event].banners[j].name
                        break

    # Apply any explicitly defined banner name changes
    for event, target_banner, change in BANNER_NAME_CHANGE:
        try:
            for banner in event_set[event].banners:
                if banner.name == target_banner:
                    banner.name = change
                    break
        except KeyError:
            pass

def sort_banners(event_set):
    # Sort the banners by date.
    for event in event_set:
        event_set[event].banners = sorted(event_set[event].banners, key=lambda banner: banner.start_date)

def merge_events(event_set, merge_event_list):
    # Merge events that are marked to be merged and delete the old events.
    for src_event, dest_event in merge_event_list.items():
        try:
            event_set[dest_event].banners.extend(event_set[src_event].banners)
            del event_set[src_event]
        except KeyError:
            pass

def fix_dates(event_set, correct_dates):
    # Fix dates for events that are marked to be fixed.
    for event_banner, dates in correct_dates.items():
        try:
            target_event, target_banner = event_banner
            start_date, end_date = dates
            for i, banner in enumerate(event_set[target_event].banners):
                if banner.name == target_banner:
                    if start_date:
                        event_set[target_event].banners[i].start_date = start_date
                    if end_date:
                        event_set[target_event].banners[i].end_date = end_date
                    event_set[target_event].banners = sorted(event_set[target_event].banners, key=lambda banner: banner.start_date)
                    break
        except KeyError:
            pass

def remove_us_suffix(event_set):
    temp_dict = {}

    # Remove the "US" suffix from the end of event names.
    for event in event_set:
        for i, banner in enumerate(event_set[event].banners):
            event_set[event].banners[i].name = re.sub(r' \(US\)', '', banner.name)
        new_event = Event(re.sub(r' \(US\)', '', event.name), event.region, event.image_file, event.banners)
        temp_dict[new_event] = new_event

    return temp_dict

def write_json(data_list, file_name):
    # Create the new version of the JSON file from the banner list.
    json_obj = jsons.dump(data_list)
    with open(os.path.join(DIR_PATH, file_name), 'w') as f:
        f.write(json.dumps(json_obj, indent=2, sort_keys=False).replace(r'\"', r'\\"').encode().decode('unicode-escape'))

def create_debug_json(event_set, region):
    debug_list = []
    for event in event_set:
        banners = []
        for banner in event.banners:
            banners.append({
                'name': banner.name,
                'start_date': banner.start_date.strftime("%-m/%-d/%Y"),
                'end_date': banner.end_date.strftime("%-m/%-d/%Y"),
                'date_origin': banner.date_origin,
                'rateups': banner.rateups,
                'num_rateups': len(banner.rateups),
            })
        debug_list.append({
            'name': event.name,
            'region': event.region,
            'image_file' : event.image_file,
            'banners': banners,
        })

    # Save the banner list to a JSON file.
    print("Saving to JSON file...")
    write_json(debug_list, "summon_data_jp.json" if region == "JP" else "summon_data_na.json")

def create_event_json(event_set_jp, event_set_na):
    used_slugs = set() # Set of slugs used
    event_list = []
    event_sets = [event_set_jp, event_set_na]
    for event_set in event_sets:
        for event in event_set:
            # Create an ID for the event.
            slug = slugify(f'{event.name}-{event.region}')
            i = 1
            while slug in used_slugs:
                slug = slugify(f'{event.name}-{event.region}-{i}')
                i += 1
            used_slugs.add(slug)

            event.slug = slug
            # Create a list to export to JSON
            event_list.append({
                'slug' : slug,
                'name' : event.name,
                'region' : event.region,
                'start_date' : event.start_date,
                'end_date' : event.end_date,
                'image_file' : event.image_file,
            })

    # Save the banner list to a JSON file.
    print("Saving to JSON file...")
    write_json(event_list, "event_data.json")

def create_banner_json(event_set_jp, event_set_na):
    used_slugs = set() # Set of slugs used
    banner_list = []
    event_sets = [event_set_jp, event_set_na]
    for event_set in event_sets:
        for event in event_set:
            for banner in event.banners:
                # Create an ID for the event.
                slug = slugify(f'{banner.name}-{event.region}')
                i = 1
                while slug in used_slugs:
                    slug = slugify(f'{banner.name}-{event.region}-{i}')
                    i += 1
                used_slugs.add(slug)

                banner.slug = slug
                # Create a list to export to JSON
                banner_list.append({
                    'slug' : slug,
                    'name' : banner.name,
                    'start_date' : banner.start_date,
                    'end_date' : banner.end_date,
                    'region' : event.region,
                    'rateups' : banner.rateups,
                    'event_id' : event.slug,
                })

    # Save the banner list to a JSON file.
    print("Saving to JSON file...")
    write_json(banner_list, "banner_data.json")

def create_servant_json(event_set_jp, event_set_na):
    servant_rateups_jp = {int(servant['id']) : [] for servant in SERVANT_DATA}
    servant_rateups_na = {int(servant['id']) : [] for servant in SERVANT_DATA}

    for event in event_set_jp:
        for banner in event.banners:
            for servant in banner.rateups:
                servant_rateups_jp[servant].append(banner.slug)

    for event in event_set_na:
        for banner in event.banners:
            for servant in banner.rateups:
                servant_rateups_na[servant].append(banner.slug)

    servant_list = []
    for servant in SERVANT_DATA:
        servant_list.append({
            'id_num' : servant['id'],
            'name' : servant['name'],
            'rarity' : servant['rarity'],
            'class_type' : servant['class_type'],
            'jp_rateups' : ','.join(servant_rateups_jp[int(servant['id'])]),
            'na_rateups' : ','.join(servant_rateups_na[int(servant['id'])]),
        })

    # Save the banner list to a JSON file.
    print("Saving to JSON file...")
    write_json(servant_list, "servant_data.json")

def parse_and_create(event_list, region):
    print("Parsing all events...")
    parse_event_lists(event_list, region)

    event_set = None
    if region == "NA":
        # Remove the "US" suffix from the end of event names.
        print("Removing US suffix...")
        event_set = remove_us_suffix(EVENT_SET_NA)
    else:
        event_set = EVENT_SET_JP

    # Merge events that are marked to be merged and delete the old events.
    print("Merging events...")
    merge_events(event_set, MERGE_EVENTS_JP if region == "JP" else MERGE_EVENTS_NA)

    # Sort the banners by date.
    print("Sorting banners by date...")
    sort_banners(event_set)

    # Remove banners with no rateups.
    print("Cleaning up empty events...")
    remove_empty(event_set)

    # Fix any banners with missing numbers.
    print("Fixing banner names...")
    fix_banner_names(event_set)

    # Fix dates for events that are marked to be fixed.
    print("Fixing dates...")
    fix_dates(event_set, CORRECT_DATES_JP if region == "JP" else CORRECT_DATES_NA)

    # Create event dates
    print(f"Extract dates for events...")
    create_event_dates(event_set)

    # Create the JSON representation for debug data
    print("Creating debug JSON data...")
    create_debug_json(event_set, region)

    return event_set

