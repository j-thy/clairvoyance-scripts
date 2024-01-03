import pywikibot
import mwparserfromhell
import wikitextparser as wtp
import jsons
import json
import os
import re
import sys
import shutil
import difflib
from tqdm import tqdm
from datetime import date
from iteration_utilities import unique_everseen

# Define format of progress bar.
BAR_FORMAT = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

# NOTE: Halloween Trilogy missing Kiyohime in first table

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
    # "Amakusagacha",
    # "Babylonia Summoning Campaign",
    "Rate Up Schedule \(Female-Servants 2\)",
    "Rate Up \(Male-Servants\)",
    "Servant Lineups",
    # "Salem Summon 2",
    # "Valentine2017 gacha rerun",
    # "Anastasia_summon_banner2",
    "■ .*? Downloads Summoning Campaign",
    # "NeroFestival2018CampaignUS",
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
)

# Wiki pages with errors that prevent parsing that should be fixed.
PAGE_FIXES = {
    'Class Specific Summoning Campaign (US)' : [r'\|(.*)}}\n\[\[', r'|\1}}\n|}\n[['], # Class Specific Summoning Campaign (US)
    'FGO Summer 2018 Event Revival (US)/Summoning Campaign' : [r'{{Marie Antoinette}}', r'{{Marie Antoinette (Caster)}}'],
    'Class Based Summoning Campaign August 2021 (US)' : [r'Knight Classes=\n(.*\n)', r'Knight Classes=\n\1! colspan=2|Rate-Up Servant List'],
    'Class Based Summoning Campaign March 2023 (US)' : [r'</tabber>', r'|}\n</tabber>'],
    'Holy Grail Front ~Moonsault Operation~/Event Info' : [r'{{!}}', r'|'],
    'Servant Summer Festival! 2018 Rerun/Main Info' : [r'=\n*<center>\n*{\|\n*\|(\[\[.*)\n*\|}\n*<\/center>', r'=\n\1\n'],
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
    "Valentine 2023 Event (US)/Summoning Campaign",
    "Class-Based Summoning Campaign (September 2019)",
    "Class-Based Summoning Campaign (March 2021)",
    "Class Based Summoning Campaign March 2023 (US)",
    "Class Based Summoning Campaign August 2021 (US)",
)

# Specify specific rateups in summoning campaigns that should not be merged into any other rateups.
NO_MERGE = {
    "GUDAGUDA Close Call 2021/Event Info" : (1,),
    "Nanmei Yumihari Hakkenden/Summoning Campaign" : (1, 2,),
    "Nahui Mictlan Chapter Release Part 2" : (1,),
    "FGO THE STAGE Camelot Release Campaign (US)" : (2,),
    "Avalon le Fae Conclusion Campaign (US)" : (1, 2,),
    "GUDAGUDA Ryouma's Narrow Escape 2023 (US)/Summoning Campaign" : (1,),
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
    "Chaldea Boys Collection 2018 Revival" : "Chaldea Boys Collection 2019",
}

# NOTE: Used by fix_banner_names()
# Change all banners' names
BANNER_NAME_FIX = {
    r"\|-\|" : "",
    r"Summoning$" : "Summoning Campaign",
    r"Summoning 1$" : "Summoning Campaign 1",
    r"Summoning 2$" : "Summoning Campaign 2",
    r"Part I Summoning Campaign" : "Summoning Campaign 1",
    r"Part II Summoning Campaign" : "Summoning Campaign 2",
    r"Summoning Campaign I$" : "Summoning Campaign 1",
    r"Summoning Campaign II$" : "Summoning Campaign 2",
    r"Summoning Campaign III$" : "Summoning Campaign 3",
    r"Summoning Campaign IV$" : "Summoning Campaign 4",
    r"Saint Quartz Summon$" : "Summoning Campaign",
    r"Saint Quartz Summon I$" : "Summoning Campaign 1",
    r"Saint Quartz Summon II$" : "Summoning Campaign 2",
    r"Summon Campaign" : "Summoning Campaign",
    r"Summoning Campaign Friend Point Summon" : "FP Summoning Campaign",
    r"Summoning Campaign Summoning Campaign" : "Summoning Campaign",
    r"Campaign Summoning Campaign" : "Summoning Campaign",
    r"Tales of Chaldean Heavy Industries" : "Chaldea Boys Collection 2023",
    r"White Day 2022" : "Chaldea Boys Collection 2022 / White Day 2022",
}

# Change specific banner names
BANNER_NAME_CHANGE = (
    # JP Events
    ("Tales of Chaldean Heavy Industries", "Chaldea Boys Collection 2023 Summoning Part 2", "Chaldea Boys Collection 2023 Summoning Campaign 1"),
    ("Singularity Repair Support Campaign", "Singularity Repair Support Summoning Campaign 7", "Singularity Repair Support Summoning Campaign 6"),
    ("Singularity Repair Support Campaign", "Singularity Repair Support Summoning Campaign 6", "Singularity Repair Support Summoning Campaign 7"),
    ("GUDAGUDA Yamatai-koku 2020 Rerun", "GUDAGUDA Yamatai-koku 2020 Rerun", "GUDAGUDA Yamatai-koku 2020 Rerun Summoning Campaign"),
    ("GUDAGUDA Yamatai-koku 2020 Rerun", "GUDAGUDA Yamatai-koku 2020 Rerun", "GUDAGUDA Yamatai-koku 2020 Rerun FP Summoning Campaign"),
    ("Avalon le Fae Chapter Release Part 2", "Avalon le Fae Chapter Release Part 2 Summoning Campaign 3", "Avalon le Fae Chapter Release Part 2 Summoning Campaign"),
    ("Slapstick Museum", "Chaldea Boys Collection 2021 Summoning Campaign", "Chaldea Boys Collection 2021 Summoning Campaign 1 & 2"),
    ("Christmas 2019 Re-Run", "Christmas 2019 Re-Run", "Christmas 2019 Re-Run Summoning Campaign"),
    ("GUDAGUDA Yamatai-koku 2020", "GUDAGUDA Yamatai-koku 2020", "GUDAGUDA Yamatai-koku 2020 Summoning Campaign"),
    ("GUDAGUDA Yamatai-koku 2020", "GUDAGUDA Yamatai-koku 2020", "GUDAGUDA Yamatai-koku 2020 FP Summoning Campaign"),
    ("Interlude Campaign 3", "Interlude Campaign 3", "Interlude Campaign 3 Summoning Campaign"),
    ("Shimosa Chapter Release", "Shimosa Chapter Release", "Shimosa Chapter Release Summoning Campaign"),
    ("Agartha Chapter Release", "Agartha Chapter Release", "Agartha Chapter Release Summoning Campaign"),
    ("SE.RA.PH", "Fate/EXTRA CCC×Fate/Grand Order", "Fate/EXTRA CCC×Fate/Grand Order Summoning Campaign"),
    ("Chaldea Boys Collection 2017", "Chaldea Boys Collection 2017", "Chaldea Boys Collection 2017 Summoning Campaign"),
    ("Valentine 2016 Event Re-Run", "Valentine 2017 Summoning Campaign", "Valentine 2017 Summoning Campaign 1"),
    ("Valentine 2016 Event Re-Run", "Valentine 2017 Summoning Campaign", "Valentine 2017 Summoning Campaign 2"),
    ("Valentine 2016 Event Re-Run", "Valentine 2017 Summoning Campaign", "Valentine 2017 Summoning Campaign (Male)"),
    ("Solomon Chapter Release", "Solomon Chapter Release", "Solomon Chapter Release Summoning Campaign"),
    ("Babylonia Chapter Release", "Babylonia Chapter Release", "Babylonia Chapter Release Summoning Campaign"),
    ("FGO 2016 Summer Event", "FGO 2016 Summer Event/Event Details Summer Event 2016 Summoning Campaign", "FGO 2016 Summer Event Summoning Campaign 1"),
    ("FGO 2016 Summer Event", "FGO 2016 Summer Event/Part II Event Details Summer Event 2016 Summoning Campaign Part II", "FGO 2016 Summer Event Summoning Campaign 2"),
    ("FGO Summer Festival 2016 ~1st Anniversary~", "FGO Summer Festival 2016 ~1st Anniversary~", "FGO Summer Festival 2016 ~1st Anniversary~ Order-Based Summoning Campaign"),
    ("Camelot Chapter Release", "Camelot Chapter Release", "Camelot Chapter Release Summoning Campaign"),
    ("Onigashima Event", "Onigashima Event", "Onigashima Event Summoning Campaign"),
    ("Journey to The West", "Journey to The West", "Journey to The West Summoning Campaign"),
    ("Fate/Accel Zero Order Event", "Fate/Accel Zero Order (Pre-Event)", "Fate/Accel Zero Order (Pre-Event) Summoning Campaign"),
    ("Fate/Accel Zero Order Event", "Fate/Accel Zero Order Event", "Fate/Accel Zero Order Event Summoning Campaign"),
    ("E Pluribus Unum Chapter Release", "E Pluribus Unum Chapter Release", "E Pluribus Unum Chapter Release Summoning Campaign"),
    ("Cries of The Vengeful Demon in the Prison Tower", "Cries of The Vengeful Demon in the Prison Tower", "Cries of The Vengeful Demon in the Prison Tower Summoning Campaign"),
    ("Saber Wars Event", "Saber Wars Event", "Saber Wars Event Summoning Campaign"),
    ("London Chapter Release", "London Summoning Campaign", "London Chapter Release Summoning Campaign"),
    ("London Chapter Release", "London Campaign 2", "London Summoning Campaign 2"),
    ("New Year Campaign 2016", "New Year Campaign 2016", "New Year Campaign 2016 Summoning Campaign"),
    ("Da Vinci-chan's Choice 2015", "Da Vinci-chan's Choice 2015", "Da Vinci-chan's Choice 2015 Summoning Campaign"),
    ("Okeanos Chapter Release", "Okeanos Summoning Campaign", "Okeanos Chapter Release Summoning Campaign"),
    # NA Events
    ("Heian-kyo Chapter Release", "Heian-kyo Summoning Campaign 2 Summoning Campaign", "Heian-kyo Summoning Campaign 2"),
    ("Fate/Grand Order Absolute Demonic Front: Babylonia Blu-ray Release Campaign Part II", "Fate/Grand Order Absolute Demonic Front: Babylonia Blu-ray Release Campaign Part II", "Fate/Grand Order Absolute Demonic Front: Babylonia Blu-ray Release Campaign Part II Summoning Campaign"),
    ("Valentine 2018 Event Revival", "Valentine 2018 Event Revival Summoning Campaign", "Valentine 2018 Event Revival Summoning Campaign (Female)"),
    ("Valentine 2018 Event Revival", "Valentine 2018 Event Revival Summoning Campaign", "Valentine 2018 Event Revival Summoning Campaign (Male)"),
)

# NOTE: Used by fix_dates()
# Change the JP banner dates
CORRECT_DATES_JP = {
    ("MELTY BLOOD: TYPE LUMINA Ushiwakamaru & Edmond Dantès Game Entry Commemorative Campaign", "MELTY BLOOD: TYPE LUMINA Ushiwakamaru & Edmond Dantès Game Entry Commemorative Summoning Campaign") : (None, date(2022, 12, 17)),
    ("Christmas 2019 Re-Run", "Christmas 2019 Re-Run Summoning Campaign") : (None, date(2020, 11, 6)),
    ("Aeaean Spring Breeze", "Chaldea Boys Collection 2020 Summoning Campaign") : (None, date(2020, 3, 20)),
    ("19M Downloads Campaign", "19M Downloads Summoning Campaign") : (None, date(2020, 3, 11)),
    ("Fate/stay night Heaven's Feel II Premiere Commemoration Campaign", "Fate/stay night Heaven's Feel II Premiere Commemoration Summoning Campaign") : (None, date(2019, 1, 25)),
    ("Christmas 2017 Event Re-Run", "Christmas 2017 Event Re-Run Summoning Campaign") : (None, date(2018, 11, 28)),
    ("Interlude Campaign 7", "Interlude Campaign 7 Summoning Campaign") : (None, date(2018, 10, 31)),
    ("14M Downloads Campaign", "14M Downloads Summoning Campaign") : (None, date(2018, 9, 12)),
    ("Servant Summer Festival! 2018", "Servant Summer Festival! 2018 Summoning Campaign 3") : (date(2018, 8, 16), None),
    ("Dead Heat Summer Race! Re-run", "Dead Heat Summer Race! Re-run Daily Special Summoning Campaign") : (date(2018, 7, 6), None),
    ("Dead Heat Summer Race! Re-run", "Dead Heat Summer Race! Re-run Summoning Campaign 2") : (date(2018, 7, 4), None),
    ("GUDAGUDA Meiji Ishin Re-run", "GUDAGUDA Meiji Ishin Re-run Summoning Campaign") : (None, date(2018, 6, 1)),
    ("Chaldea Boys Collection 2018", "Chaldea Boys Collection 2018 Summoning Campaign") : (None, date(2018, 3, 21)),
    ("Kara no Kyoukai Collaboration Event Re-run", "Kara no Kyoukai Collaboration Event Re-run Summoning Campaign") : (None, date(2018, 3, 1)),
    ("Fate/EXTRA Last Encore Anime Broadcast Commemoration Campaign", "Fate/EXTRA Last Encore Anime Broadcast Commemoration Summoning Campaign") : (None, date(2018, 2, 11)),
    ("Da Vinci and The 7 Counterfeit Heroic Spirits Rerun Lite Ver", "Da Vinci and The 7 Counterfeit Heroic Spirits Rerun Lite Ver Summoning Campaign") : (None, date(2018, 1, 24)),
    ("Christmas 2016 Event Re-run", "Christmas 2016 Event Re-run Summoning Campaign") : (None, date(2017, 11, 29)),
    ("Shimosa Chapter Release", "Shimosa Chapter Release Summoning Campaign") : (None, date(2017, 11, 1)),
    ("Fate/stay night Heaven's Feel Premiere Commemoration Campaign", "Fate/stay night Heaven's Feel Premiere Commemoration Summoning Campaign") : (None, date(2017, 10, 22)),
    ("Dead Heat Summer Race!", "Dead Heat Summer Race! Daily Special Summoning Campaign") : (date(2017, 8, 24), None),
    ("Dead Heat Summer Race!", "Dead Heat Summer Race! Summoning Campaign 2") : (date(2017, 8, 16), None),
    ("FGO 2016 Summer Event Re-Run", "FGO 2016 Summer Event Re-Run Summoning Campaign 2") : (date(2017, 7, 20), None),
    ("Rashomon Event Rerun", "Rashomon Event Rerun Summoning Campaign") : (None, date(2017, 6, 14)),
    ("9M Downloads Campaign", "9M Downloads Summoning Campaign") : (None, date(2017, 6, 7)),
    ("SE.RA.PH", "SE.RA.PH Summoning Campaign 2") : (date(2017, 5, 10), None),
    ("SE.RA.PH", "Fate/EXTRA CCC×Fate/Grand Order Summoning Campaign") : (None, date(2017, 5, 3)),
    ("Valentine 2016 Event Re-Run", "Valentine 2017 Summoning Campaign 2") : (date(2017, 2, 11), None),
    ("Moon Goddess Event Re-Run", "Moon Goddess Event Re-Run Summoning Campaign") : (None, date(2017, 1, 30)),
    ("Solomon Chapter Release", "Solomon Chapter Release Summoning Campaign") : (None, date(2016, 12, 31)),
    ("Amakusa Shirō Summoning Campaign", "Amakusa Shirō Summoning Campaign") : (None, date(2016, 12, 7)),
    ("FGO 2016 Summer Event", "FGO 2016 Summer Event Summoning Campaign 2") : (date(2016, 8, 22), None),
    ("Camelot Chapter Release", "Camelot Chapter Release Summoning Campaign") : (None, date(2016, 7, 29)),
    ("E Pluribus Unum Chapter Release", "E Pluribus Unum Chapter Release Summoning Campaign") : (None, date(2016, 4, 13)),
    ("AnimeJapan 2016 Exhibition Commemoration Campaign", "AnimeJapan 2016 Exhibition Commemoration Summoning Campaign") : (date(2016, 3, 23), date(2016, 3, 30)),
    ("New Year Campaign 2016", "New Year Campaign 2016 Summoning Campaign") : (None, date(2016, 1, 7)),
    ("4M Downloads Campaign", "4M Downloads Summoning Campaign") : (None, date(2015, 10, 14)),
}

# Change the NA banner dates
CORRECT_DATES_NA = {
    # GUDAGUDA Yamataikoku 2022 Revival Summoning Campaign 2 - Start: 10/31/2023
    # Halloween 2023 Event Summoning Campaign 3 - Start: 10/19/2023
    # Halloween Trilogy Event Summoning Campaign - End: 10/12/2023
    # Fate/Samurai Remnant Release Summoning Campaign - End: 10/8/2023
    # Interlude Campaign 17 Summoning Campaign - End: 10/4/2023
    # FGO Summer 2023 Event Summoning Campaign 3 - Start: 9/6/2023
    # FGO Summer 2023 Event Summoning Campaign 4 - Start: 9/13/2023
    # Back to School Campaign 2023 Summoning Campaign - End: 8/28/2023
    # Grand Nero Festival 2023 Summoning Campaign 2 - Start: 8/6/2023
    # Avalon le Fae Conclusion Summoning Campaign 3 - Start: 7/24/2023, End: 7/31/2023
    # Avalon le Fae Conclusion Summoning Campaign 2 - Start: 7/17/2023, End: 7/31/2023
    # Avalon le Fae Conclusion Summoning Campaign 1 - Start: 7/12/2023, End: 7/26/2023
    # FGO 6th Anniversary Commemorative Summoning Campaign - End: 7/2/2023
    # Avalon le Fae Part 2 Chapter Release Summoning Campaign - End: 7/2/2023
    # Interlude Campaign 16 Summoning Campaign - End: 6/29/2023
    # Avalon le Fae Part 1 Chapter Release Summoning Campaign - End: 6/19/2023
    # Avalon le Fae Pre-Release Summoning Campaign - End: 6/15/2023
    # FGO Summer 2022 Event Revival Summoning Campaign 3 - Start: 5/22/2023
    # My Super Camelot 2023 Pre-Release Summoning Campaign - End: 5/8/2023
    # FGO Waltz in the Moonlight Collaboration Event Summoning Campaign 2 - Start: 4/20/2023, End: 5/5/2023
    # Chaldea Boys Collection 2023 Summoning Campaign 1 - End: 3/16/2023
    # Spring has Sprung Campaign 2023 Summoning Campaign - End: 3/9/2023
    # Saber Wars II Revival Summoning Campaign 2 - Start: 1/11/2023, End: 1/25/2023
    # Happy New Year 2023 Summoning Campaign 2 - Start: 1/2/2023, End: 1/9/2023
    # Christmas 2022 Event Summoning Campaign 2 - Start: 12/18/2022, End: 12/26/2022
    # 19M Downloads Summoning Campaign - End: 12/19/2022
    # Interlude Campaign 15 Summoning Campaign - End: 12/11/2022
    # Heian-kyo Chapter Release Summoning Campaign - End: 12/4/2022
    # Heian-kyo Pre-Release Summoning Campaign - End: 11/20/2022
    # Imaginary Scramble Summoning Campaign 2 - Start: 11/3/2022, End: 11/13/2022
    # Imaginary Scramble Pre-Release Summoning Campaign - End: 11/7/2022
    # Christmas 2021 Event Revival Summoning Campaign - End: 10/19/2022
    # FGO THE STAGE Solomon Release Summoning Campaign - End: 10/5/2022
    # Interlude Campaign 14 Summoning Campaign - End: 8/30/2022
    # 18M Downloads Summoning Campaign - End: 8/23/2022
    # FGO Summer 2022 Event Summoning Campaign 4 - Start: 7/25/2022, End: 8/6/2022
    # FGO Summer 2022 Event Summoning Campaign 3 - Start: 7/18/2022
    # FGO 5th Anniversary Pre-Anniversary Summoning Campaign - End: 6/23/2022
    # SE.RA.PH Main Interlude Release Summoning Campaign - End: 7/4/2022
    # FGO Summer 2021 Event Revival Summoning Campaign 3 - Start: 5/29/2022
    # FGO Summer 2021 Event Revival Summoning Campaign 2 - Start: 5/29/2022
    # GUDAGUDA Final Honnoji 2021 Revival Summoning Campaign 2 - Start: 4/24/2022, End: 5/4/2022
    # 17M Downloads Summoning Campaign - Start: 4/10/2022, End: 4/27/2022
    # Olympus Chapter Release Summoning Campaign - End: 4/6/2022
    # Chaldea Boys Collection 2022 Summoning Campaign - End: 3/13/2022
    # 16M Downloads Summoning Campaign - End: 2/27/2022
    # Interlude Campaign 12 Summoning Campaign - End: 2/9/2022
    # New Year 2021 Event Revival Summoning Campaign 2 - Start: 1/10/2022, End: 1/24/2022
    # Happy New Year 2022 Summoning Campaign - End: 1/15/2022
    # Christmas 2021 Event Summoning Campaign - End: 12/31/2021
    # Atlantis Chapter Release Summoning Campaign - End: 12/14/2021
    # FGO Thanksgiving Special 2021 Summoning Campaign - End: 12/1/2021
    # Interlude Campaign 11 Summoning Campaign - End: 11/29/2021
    # Early Winter Campaign 2021 Summoning Campaign - End: 11/22/2021
    # 15M Downloads Summoning Campaign - End: 11/8/2021
    # Saber Wars II Summoning Campaign 2 - Start: 10/23/2021, End: 11/6/2021
    # Saber Wars II Pre-Release Summoning Campaign - End: 10/31/2021
    # FGO THE STAGE Camelot Release Summoning Campaign 2 - Start: 9/24/2021, End: 10/3/2021
    # FGO THE STAGE Camelot Release Summoning Campaign 1 - End: 9/24/2021
    # FGO Summer 2021 Event Summoning Campaign 3 - Start: 8/4/2021
    # FGO Summer 2021 Event Summoning Campaign 2 - Start: 8/1/2021, End: 8/15/2021
    # FGO Summer 2020 Event Revival Summoning Campaign 3 - Start: 7/18/2021
    # FGO Festival 2021 ~4th Anniversary~ Summoning Campaign - End: 7/17/2021
    # 14M Downloads Summoning Campaign - End: 6/30/2021
    # Yugakshetra Chapter Release Summoning Campaign - End: 6/16/2021
    # Interlude Campaign 9 Summoning Campaign - End: 6/10/2021
    # Fate/Grand Order Absolute Demonic Front: Babylonia Blu-ray Release Summoning Campaign - End: 4/12/2021
    # Tokugawa Restoration Labyrinth Summoning Campaign 2 - Start: 3/28/2021, End: 4/11/2021
    # Chaldea Boys Collection 2021 Summoning Campaign - End: 3/21/2021
    # Fate/Extra CCC Collaboration Event Revival Summoning Campaign 2 - Start: 2/22/2021, End: 3/8/2021
    # Even More Learning With Manga Release Celebration Summoning Campaign - End: 1/27/2021
    # New Year 2021 Event Summoning Campaign 2 - Start: 1/7/2021, End: 1/21/2021
    # Happy New Year 2021 Summoning Campaign - End: 1/15/2021
    # SIN Chapter Release Summoning Campaign - End: 12/9/2020
    # Fate/Stay Night Heaven's Feel III Theatrical Release Commemorative Summoning Campaign - End: 11/25/2020
    # Christmas 2019 Event Revival Summoning Campaign - End: 11/25/2020
    # Interlude Campaign 7 Summoning Campaign - End: 11/15/2020
    # FGO Summer 2020 Event Summoning Campaign 3 - Start: 8/9/2020
    # FGO Summer 2019 Event Revival Summoning Campaign 3 - Start: 7/24/2020
    # FGO Summer 2019 Event Revival Summoning Campaign 2 - Start: 7/23/2020
    # FGO Festival 2020 ~3rd Anniversary~ Summoning Campaign - End: 7/20/2020
    # Götterdämmerung Chapter Release Summoning Campaign - End: 7/6/2020
    # GUDAGUDA Meiji Restoration Revival Summoning Campaign - End: 5/21/2020
    # Fate/Apocrypha Event Pre-Release Summoning Campaign - End: 5/4/2020
    # Anastasia Chapter Release Summoning Campaign - End: 4/9/2020
    # Chaldea Boys Collection 2020 Summoning Campaign - End: 3/19/2020
    # The Garden of Sinners Collaboration Event Revival Summoning Campaign - End: 3/2/2020
    # The Tale of Setsubun Summoning Campaign - End: 2/9/2020
    # Da Vinci and the 7 Counterfeit Heroic Spirits Revival Summoning Campaign - End: 1/23/2020
    # Happy New Year 2020 Summoning Campaign - End: 1/19/2020
    # Salem Chapter Release Summoning Campaign - End: 12/15/2019
    # FGO Thanksgiving Special 2019 Summoning Campaign - End: 12/2/2019
    # Christmas 2018 Event Revival Summoning Campaign - End: 11/26/2019
    # 8M Downloads Summoning Campaign - End: 11/21/2019
    # Shimousa Chapter Release Summoning Campaign - End: 10/28/2019
    # FGO Summer 2019 Event Summoning Campaign 3 - Start: 8/12/2019
    # FGO Summer 2019 Event Summoning Campaign 2 - Start: 8/5/2019
    # FGO Summer 2018 Event Revival Summoning Campaign 2 - Start: 7/19/2019
    # FGO Festival 2019 ~2nd Anniversary~ Summoning Campaign - Start: 7/6/2019, End: 7/23/2019
    # Agartha Chapter Release Summoning Campaign - End: 7/6/2019
    # Rashomon Event Revival Summoning Campaign - End: 6/6/2019
    # Fate/Extra CCC Collaboration Event Summoning Campaign 2 - Start: 5/1/2019, End: 5/15/2019
    # Fate/Extra CCC Event Pre-Release Summoning Campaign - End: 4/22/2019
    # Shinjuku Chapter Release Summoning Campaign - End: 3/11/2019
    # 5M Downloads Summoning Campaign - End: 2/6/2019
    # Moon Goddess Event Revival Summoning Campaign - End: 1/30/2019
    # Solomon Chapter Release Summoning Campaign - End: 12/31/2018
    # Babylonia Chapter Release Summoning Campaign - End: 12/31/2018
    # Christmas 2018 Event Summoning Campaign 2 - Start: 12/2/2018, End: 12/12/2018
}

# NOTE: Used by parse_event_lists()
# Skip parsing certain dates in event list
SKIP_DATES = {
    "Event List/2016 Events": ["|August 22 ~ August 31"],
    "Event List/2017 Events": ["|August 17 ~ September 1", "|July 20 ~ July 29"],
    "Event List/2018 Events": ["|July 4 ~ July 13"],
    "Event List (US)/2017 Events": ["|July 13 ~ July 20"],
    "Event List (US)/2018 Events": ["|August 6 ~ August 14"],
    "Event List (US)/2019 Events": ["|August 5 ~ August 20", "|July 19 ~ July 28"],
    "Event List (US)/2020 Events": ["|July 23 ~ August 1"],
}

# Include certain subpages in an event
INCLUDE_SUBPAGES = {
    "FGO 2016 Summer Event" : ["FGO 2016 Summer Event/Event Details", "FGO 2016 Summer Event/Part II Event Details"],
    "SE.RA.PH" : ["Fate/EXTRA CCC×Fate/Grand Order"],
    "FGO 2016 Summer Event Re-Run" : ["FGO 2016 Summer Event Re-Run/Event Info"],
    "Dead Heat Summer Race!" : ["Dead Heat Summer Race!/Event Info"],
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
)

class Event:
    def __init__(self, name, region, banners):
        self.name = name
        self.region = region
        self.banners = banners
    
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
    
    def copy_metadata(self, other):
        self.name = other.name
        self.start_date = other.start_date
        self.end_date = other.end_date
        self.date_origin = other.date_origin


TESTING = 0 # Whether the script is being run in testing mode
SERVANT_DATA = None # Servant data
DIR_PATH = os.path.dirname(__file__) # Path to the directory of this file
SITE = pywikibot.Site() # Wiki site
EVENT_SET_JP = {} # Dictionary of banners for JP
EVENT_SET_NA = {} # Dictionary of banners for NA
CURRENT_YEAR = 0 # Current year
CURRENT_REGION = "" # Current region

# Check if the script is being run in testing mode.
if len(sys.argv) > 1:
    TESTING = int(sys.argv[1])

# Import the servant data.
with open(os.path.join(DIR_PATH, 'servant_data.json')) as f:
    SERVANT_DATA = jsons.loads(f.read())

# Get the names and IDs of all the servants.
SERVANT_NAMES = {SERVANT_DATA[servant]['name'] : int(SERVANT_DATA[servant]['id']) for servant in SERVANT_DATA}

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

    # Return the date range
    return (date(year, start_month, start_day), date(year, end_month, end_day)) if end_month >= start_month \
        else (date(year, start_month, start_day), date(year+1, end_month, end_day))

# Split date strings into start and end dates
def date_splitter(date_str):
    date_split = date_str.split("~")
    if len(date_split) == 1:
        date_split = date_split[0].split("-")
    if len(date_split) == 1:
        date_split = date_split[0].split("～")
    
    return date_split

# Parse an FGO wiki page
def parse(event_set, page, duration, parent=None):
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

    # Do not parse explicitly excluded pages and user blogs.
    if title in EXCLUDE_PAGES or title.startswith("User blog:"):
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
            if class_type != 'wikitable' or not any([x in tag for x in TABLE_MATCHES]):
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
            new_event = Event(parent, CURRENT_REGION, banners)
            event_set[new_event] = new_event
    # If the event is not in the set, add it
    else:
        new_event = Event(title, CURRENT_REGION, banners)
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
            parse(event_set, summon_page, date, parent_title)

            # Check another level of subpages
            rec_check_subpages(event_set, summon_page, date, parent_title)
            # Remove any pre-release events with rateups that are already in the main event
            pre_release_remove(event_set)

# Parse test pages
def parse_test():
    file_name = "Christmas2023.png"
    page = pywikibot.FilePage(SITE, file_name)
    # If the directory "imgs" does not already exist, create it.
    if not os.path.exists("imgs"):
        os.makedirs("imgs")
    test = page.download(filename=f'imgs/{file_name}.!')
    print(page)

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

        # Reverse events and date list since events in the event list are listed from newest to oldest
        events.reverse()
        date_list.reverse()
        # Create a dict where the key is the event name and the value is the date of the event.
        events = dict(zip(events, date_list))

        # Parse each event
        for event, date in (pbar := tqdm(events.items(), bar_format=BAR_FORMAT)):
            pbar.set_postfix_str(event)

            # Open the event page
            event_page = pywikibot.Page(SITE, event)
            # Parse the event page
            parse(event_set, event_page, date)

            # Parse any explicitly defined subpages of the event page
            if event_page.title() in INCLUDE_SUBPAGES:
                for subpage in INCLUDE_SUBPAGES[event_page.title()]:
                    # Open the subpage
                    summon_page = pywikibot.Page(SITE, subpage)
                    # Parse the subpage and set the parent to the event page
                    parse(event_set, summon_page, date, event_page.title())
                    # Remove any pre-release events with rateups that are already in the main event
                    pre_release_remove(event_set)

            # Recursively find any summoning campaign subpages
            if event not in ADD_EMPTY_ENTRY:
                rec_check_subpages(event_set, event_page, date, event_page.title())

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
        # Check each banner title
        for i, banner_title in enumerate(banner_titles):
            # Apply any explicitly defined fixes
            for original, replace in BANNER_NAME_FIX.items():
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
        new_event = Event(re.sub(r' \(US\)', '', event.name), event.region, event.banners)
        temp_dict[new_event] = new_event

    return temp_dict

def parse_and_create(event_list, event_set, region):
    print("Parsing all events...")
    parse_event_lists(event_list, region)

    if region == "NA":
        # Remove the "US" suffix from the end of event names.
        print("Removing US suffix...")
        event_set = remove_us_suffix(event_set)

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

    # Create the JSON representation
    print("Creating JSON data...")
    event_list = []
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
        event_list.append({
            'name': event.name,
            'region': event.region,
            'banners': banners,
        })

    # Save the banner list to a JSON file.
    print("Saving to JSON file...")
    # Filenames for the old and new JSON files.
    FILE_OLD = "summon_data_old.json" if region == "JP" else "summon_data_old_na.json"
    FILE_NEW = "summon_data.json" if region == "JP" else "summon_data_na.json"

    # Save the old version of the JSON file for diff comparison.
    shutil.copy(os.path.join(DIR_PATH, FILE_NEW), os.path.join(DIR_PATH, FILE_OLD))

    # Create the new version of the JSON file from the banner list.
    json_obj = jsons.dump(event_list)
    with open(os.path.join(DIR_PATH, FILE_NEW), 'w') as f:
        f.write(json.dumps(json_obj, indent=2, sort_keys=False))

    # Write the diff between the old and new banner list JSON to a file.
    with open(os.path.join(DIR_PATH, FILE_NEW), 'r') as f1:
        with open(os.path.join(DIR_PATH, FILE_OLD), 'r') as f2:
            diff = difflib.unified_diff(f2.readlines(), f1.readlines())
            with open(os.path.join(DIR_PATH, 'diff.txt' if region == "JP" else 'diff_na.txt'), 'w') as f3:
                f3.writelines(diff)

# If TESTING is 1, parse the test pages. Otherwise, parse the Summoning Campaign category.
if TESTING == 1:
    parse_test()
    sys.exit(0)

parse_and_create(EVENT_LIST_NA, EVENT_SET_NA, "NA")
parse_and_create(EVENT_LIST_JP, EVENT_SET_JP, "JP")
