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
from collections import OrderedDict

# Define format of progress bar.
BAR_FORMAT = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

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
    "Limited Servants", # S I N Summoning Campaign 2
    "Edmond Dantès]] {{LimitedS}}\n|{{Avenger}}\n|-\n|4{{Star}}\n|{{Gilgamesh (Caster)", # Servant Summer Festival! 2018/Event Info
)

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

# Keywords before a section of text that should be removed before any parsing is done.
PRIORITY_REMOVE_MATCHES = (
    "CBC 2022=",
    "{{Napoléon}} {{Valkyrie}} {{Thomas Edison}}", # WinFes 2018/19 Commemoration Summoning Campaign
    "Craft Essences are now unique per party, allowing Servants in multiple parties to hold different Craft Essences", # London Chapter Release
    r"==New \[\[Friend Point\]\] Gacha Servants==",
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

# Pages with wikitables that can generate false positives so table-style parsing should be skipped.
SKIP_TABLE_PARSE_PAGES = (
    "Prisma Codes Collaboration Event (US)/Summoning Campaign",
)

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

# Pages with multiple rateups that should be merged into one regardless of whether there are common servants.
FORCE_MERGE = (
    "Fate/Apocrypha Collaboration Event Revival (US)/Summoning Campaign",
    "Chaldea Boys Collection 2023 (US)",
    "Valentine 2023 Event (US)/Summoning Campaign",
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

# Servant names that are incorrect on the wiki that should be fixed.
NAME_FIXES = {
    'Attila' : 'Altera', # FGO Summer Festival 2016 ~1st Anniversary~
    "EMIYA (Alter) NA" : "EMIYA (Alter)",
    "Jaguar Warrior" : "Jaguar Man",
}

# Rateup servants that are missing from the banner on the wiki that should be fixed.
RATEUP_FIXES = {
    'S I N Chapter Release' : 'Jing Ke', # S I N Chapter Release
}

# Wiki pages with errors that prevent parsing that should be fixed.
PAGE_FIXES = {
    'Class Specific Summoning Campaign (US)' : [r'\|(.*)}}\n\[\[', r'|\1}}\n|}\n[['], # Class Specific Summoning Campaign (US)
    'FGO Summer 2018 Event Revival (US)/Summoning Campaign' : [r'{{Marie Antoinette}}', r'{{Marie Antoinette (Caster)}}'],
    'Class Based Summoning Campaign August 2021 (US)' : [r'Knight Classes=\n(.*\n)', r'Knight Classes=\n\1! colspan=2|Rate-Up Servant List'],
    'Class Based Summoning Campaign March 2023 (US)' : [r'</tabber>', r'|}\n</tabber>'],
    'Holy Grail Front ~Moonsault Operation~/Event Info' : [r'{{!}}', r'|'],
}

SKIP_DURATION_PARSE = (
    "SE.RA.PH",
)

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

SUBPAGE_TITLE_REMOVE = (
    "/Event Info",
    "/Event_Info",
    "/Main Info",
    "/Main_Info",
    "/Event Summary",
    "/Info",
)

SUBPAGE_TITLE_REPLACE = (
    "/Summoning",
    "/Summon",
    "/FP",
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

# NOTE: Halloween Trilogy missing Kiyohime in first table
# TODO: Strange Fake -Whispers of Dawn- Broadcast Commemoration Campaign -> Strange Fake -Whispers of Dawn- Broadcast Commemoration Summoning Campaign
# TODO: Ordeal Call Release Campaign -> Ordeal Call Pre-Release Campaign
# TODO: Lilim Harlot -> FGO Arcade Collaboration Pre-Release Campaign
# TODO: Nahui Mictlan Chapter Release Part 2 -> Nahui Mictlan Lostbelt Part II Pre-Release Campaign
# TODO: Chaldea Faerie Knight Cup -> Chaldea Faerie Knight Cup Pre-Release Campaign
# TODO: Fate/Grand Order ～7th Anniversary～ -> Fate/Grand Order ～7th Anniversary～ Countdown Campaign
# TODO: Avalon le Fae Chapter Release -> Avalon le Fae Lostbelt Pre-Release Campaign
# TODO: Slapstick Museum -> Chaldea Boys Collection 2021
# TODO: Olympus Summoning Campaign 2 -> Olympus Chapter Release
# TODO: Yuga Kshetra Summoning Campaign 2 -> Yuga Kshetra Chapter Release
# TODO: Yuga Kshetra Pre-Release Campaign -> Yuga Kshetra Chapter Release
# TODO: The Antiquated Spider Nostalgically Spins Its Thread -> Chaldea Boys Collection 2019
# TODO: WinFes 2018/19 Commemoration Summoning Campaign 2 -> WinFes 2018/19 Commemoration Campaign: Osaka
# TODO: S I N Summoning Campaign 2 -> S I N Chapter Release
# TODO: Götterdämmerung Lostbelt Pre-Release Campaign -> Götterdämmerung Chapter Release
# TODO: Anastasia Summoning Campaign 2 -> Anastasia Chapter Release
# TODO: Salem Summoning Campaign 2 -> Salem Chapter Release
# TODO: Shimosa Summoning Campaign 2 -> Shimosa Chapter Release
# TODO: Agartha Summoning Campaign 2 -> Agartha Chapter Release
# TODO: Shinjuku Summoning Campaign 2 -> Shinjuku Chapter Release
# TODO: Babylonia Summoning Campaign 2 -> Babylonia Chapter Release
# TODO: Camelot Summoning Campaign 2 -> Camelot Chapter Release
# TODO: Fate/Accel Zero Order (Pre-Event) -> Fate/Accel Zero Order Event

# TODO: Correct:
# MELTY BLOOD: TYPE LUMINA Ushiwakamaru & Edmond Dantès Game Entry Commemorative Campaign
# Christmas 2019 Re-Run
# 19M Downloads Campaign
# Servant Summer Festival! 2018 Rerun (maybe regex fix)
# Christmas 2017 Event Re-Run
# Interlude Campaign 7
# Battle in New York 2018
# 14M Downloads Campaign
# Servant Summer Festival! 2018
# Dead Heat Summer Race! Re-run
# GUDAGUDA Meiji Ishin Re-run
# Chaldea Boys Collection 2018
# Kara no Kyoukai Collaboration Event Re-run
# Fate/EXTRA Last Encore Anime Broadcast Commemoration Campaign
# Da Vinci and The 7 Counterfeit Heroic Spirits Rerun Lite Ver
# 11M Downloads Campaign (maybe regex edit)
# Christmas 2016 Event Re-run
# Halloween 2017 Event
# Shimosa Chapter Release
# Fate/stay night Heaven's Feel Premiere Commemoration Campaign
# Dead Heat Summer Race!
# FGO 2016 Summer Event Re-Run
# Rashomon Event Rerun
# 9M Downloads Campaign
# SE.RA.PH
# Valentine 2016 Event Re-Run
# Moon Goddess Event Re-Run
# Solomon Chapter Release
# FGO 2016 Summer Event
# Camelot Chapter Release
# Fate/Accel Zero Order Event
# Da Vinci and The 7 Counterfeit Heroic Spirits
# E Pluribus Unum Chapter Release
# AnimeJapan 2016 Exhibition Commemoration Campaign
# New Year Campaign 2016
# 4M Downloads Campaign
INCLUDE_SUBPAGES = {
    "FGO 2016 Summer Event" : ["FGO 2016 Summer Event/Event Details", "FGO 2016 Summer Event/Part II Event Details"],
    "SE.RA.PH" : ["Fate/EXTRA CCC×Fate/Grand Order"],
    "FGO 2016 Summer Event Re-Run" : ["FGO 2016 Summer Event Re-Run/Event Info"],
    "Dead Heat Summer Race!" : ["Dead Heat Summer Race!/Event Info"],
    "Setsubun 2018" : ["Setsubun 2018/Main Info"],
    "Dead Heat Summer Race! Re-run" : ["Dead Heat Summer Race! Re-run/Event Info"],
    "FGO Summer 2018 Event (US)" : ["FGO Summer 2018 Event (US)/Summoning Campaign"],
    "Servant Summer Festival! 2018" : ["Servant Summer Festival! 2018/Event Info"],
    "FGO Summer 2018 Event Revival (US)" : ["FGO Summer 2018 Event Revival (US)/Summoning Campaign"],
    "Servant Summer Festival! 2018 Rerun" : ["Servant Summer Festival! 2018 Rerun/Main Info"],
    "FGO Summer 2019 Event (US)" : ["FGO Summer 2019 Event (US)/Summoning Campaign"],
    "Halloween 2018 Event Revival (US)" : ["Halloween 2018 Event Revival (US)/Summoning Campaign"],
    "The Tale of Setsubun (US)" : ["The Tale of Setsubun (US)/Summoning Campaign"],
    "FGO Summer 2019 Event Revival (US)" : ["FGO Summer 2019 Event Revival (US)/Summoning Campaign"],
}

# Test pages to parse.
TEST_PAGES = (
    "Fate/Apocrypha Collaboration Event Revival (US)/Summoning Campaign",
)

# List of Event Pages. TODO: Can probably replace later with just parsing event list page.
# If it is 0, parse wikinlinks
# If it is 1, parse templates
EVENT_LISTS = (
    "Event List/2015 Events",
    "Event List/2016 Events",
    "Event List/2017 Events",
    "Event List/2018 Events",
    "Event List/2019 Events",
    "Event List/2020 Events",
    "Event List/2021 Events",
    "Event List/2022 Events",
    "Event List/2023 Events",
    # "Event List (US)/2017 Events",
    # "Event List (US)/2018 Events",
    # "Event List (US)/2019 Events",
    # "Event List (US)/2020 Events",
    # "Event List (US)/2021 Events",
    # "Event List (US)/2022 Events",
    # "Event List (US)/2023 Events",
)

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

MONTH_TRANSLATE = {
    "January" : "1",
    "Jan" : "1",
    "February" : "2",
    "Feb" : "2",
    "March" : "3",
    "Mar" : "3",
    "April" : "4",
    "Apr" : "4",
    "May" : "5",
    "June" : "6",
    "Jun" : "6",
    "July" : "7",
    "Jul" : "7",
    "August" : "8",
    "Aug" : "8",
    "September" : "9",
    "Sept" : "9",
    "October" : "10",
    "Oct" : "10",
    "November" : "11",
    "Nov" : "11",
    "December" : "12",
    "Dec" : "12",
}

SKIP_DATES = {
    "Event List/2016 Events": ["|August 22 ~ August 31"],
    "Event List/2017 Events": ["|August 17 ~ September 1", "|July 20 ~ July 29"],
    "Event List/2018 Events": ["|July 4 ~ July 13"],
    "Event List (US)/2017 Events": ["|July 13 ~ July 20"],
    "Event List (US)/2018 Events": ["|August 6 ~ August 14"],
    "Event List (US)/2019 Events": ["|August 5 ~ August 20", "|July 19 ~ July 28"],
    "Event List (US)/2020 Events": ["|July 23 ~ August 1"],
}

FAKE_BANNERS = (
    "MELTY BLOOD: TYPE LUMINA Mashu's Game Entry Commemorative Campaign",
)

# Read in test parameter from command line.
TESTING = 0
if len(sys.argv) > 2:
    TESTING = int(sys.argv[2])

# Import the servant data and get the names of all the servants.
DIR_PATH = os.path.dirname(__file__)
SERVANT_DATA = None
with open(os.path.join(DIR_PATH, 'servant_data.json')) as f:
    SERVANT_DATA = jsons.loads(f.read())
SERVANT_NAMES = set([SERVANT_DATA[servant]['name'] for servant in SERVANT_DATA])

# Get the FGO wiki site.
# Initialize the summoning campaign and event dictionaries.
SITE = pywikibot.Site()
BANNER_DICT_JP = OrderedDict()
BANNER_DICT_NA = OrderedDict()
CURRENT_YEAR = 0
CURRENT_REGION = ""

# Finds indexes of matching keywords in order to breaks link-style pages into chunks, each ideally with a rateup.
def search_text(text):
    splits = {}

    # Find index of keywords that indicate a rateup coming after. Mark it to be preserved.
    for string in LINK_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            splits[match.start()] = True
    
    # Find index of keywords that are before sections causing false positives. Mark it to be removed.
    for string in REMOVE_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            splits[match.start()] = False
    
    # Sort the indexes of the splits and return it.
    splits = {k: v for k, v in sorted(splits.items(), key=lambda item: item[0], reverse=True)}
    return splits

# Fix any errors in the servant name.
def correct_name(text):
    if text in NAME_FIXES:
        return NAME_FIXES[text]
    return text

def date_parser(start_date, end_date):
    start_date_str = start_date.split(",")[0].strip().split(" ")
    end_date_str = end_date.split(",")[0].strip().split(" ")
    start_month = MONTH_TRANSLATE[start_date_str[0]]
    start_day = int(re.sub(r'[a-zA-Z]', '', start_date_str[1]))
    try:
        end_month = MONTH_TRANSLATE[end_date_str[0]]
        end_day = int(re.sub(r'[a-zA-Z]', '', end_date_str[1]))
    except KeyError:
        end_month = start_month
        end_day = start_day

    return f'{start_month}/{start_day}-{end_month}/{end_day}'

# Parse a wiki page
def parse(banner_dict, page, event_date, parent=None):
    # Get the title of the page
    title = page.title()

    # Do not parse pages that are marked no-parse/no-merge or no-parse/mergeable or title starts with "User blog:"
    if title in EXCLUDE_PAGES or title.startswith("User blog:"):
        return

    # Get contents of the page
    text = page.text
    # Remove HTML comments
    text = re.sub(r'<!--(.|\n)*?-->', '', text)

    # Apply any explicitly defined fixes
    if title in PAGE_FIXES:
        text = re.sub(PAGE_FIXES[title][0], PAGE_FIXES[title][1], text)

    # Apply any priority text removals, removing the match and everything after it.
    for string in PRIORITY_REMOVE_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            text = text[:match.start()]

    # Parse the text
    wikicode = mwparserfromhell.parse(text)

    # Initialize the list of rateups.
    banners = []

    # Find and parse the rateup servants wikitable, unless the page is explicitly marked to skip this.
    if title not in SKIP_TABLE_PARSE_PAGES:
        # Get all the tags in the page, any of which may contain the rateup servants wikitable.
        tags = wikicode.filter_tags()

        cntr = 0
        # Find any tags containing the rateup servants wikitable.
        for tag in tags:
            # For the tag to contain a valid rateup servants wikitable,
            # 1. The tag must have a "class" field.
            # 2. The "class" field must contain "wikitable".
            # 3. The tag must contain at least one keyword indicating that it is a rateup servants wikitable.
            class_type = None
            try:
                class_type = tag.get("class").value.strip()
            except ValueError:
                pass
            if class_type != 'wikitable' or not any([x in tag for x in TABLE_MATCHES]):
                continue

            # Parse the tag
            table = mwparserfromhell.parse(tag)

            # Get all the templates ( {{wikipage}} ) in the tag.
            templates = table.filter_templates()

            # Initialize the list of rateup servants.
            rateup_servants = [] # CBC 2016 ~ 2019 Craft Essences Summoning Campaign

            # Get the rateup servants from the templates ( {{servant_name}} )
            for template in templates:
                # Fix any errors in the servant name
                name = correct_name(str(template.name))

                # Add the servant name to the list of rateup servants if it is a valid servant name.
                if name in SERVANT_NAMES:
                    rateup_servants.append(name)
            
            # Manually add any rateup servants that are incorrectly left out of the table on the wiki
            for string in RATEUP_FIXES:
                if string == title:
                    rateup_servants.append(RATEUP_FIXES[string])

            # If rateup servants were found...
            if rateup_servants:
                # Sort the servants alphabetically.
                rateup_servants.sort()
                # Remove duplicates.
                rateup_servants = tuple(dict.fromkeys(rateup_servants))
                # Append to the list of rateups.
                banners.append(rateup_servants)
                # If the rateup that was just added and the previous rateup have any servants in common, merge the new one into the previous one.
                # Also, merge any banners that are forced to be merged.
                # Don't merge if the whole page is marked not to be merged or a specific rateup is marked not to be merged.
                if len(banners) > 1 and (title in FORCE_MERGE or (len(set(banners[-2]).intersection(set(banners[-1]))) > 0 and not (title in NO_MERGE and cntr in NO_MERGE[title]))): # GUDAGUDA Close Call 2021/Event Info
                    # Remove duplicates from the merged banner and sort it.
                    banners[-2] = tuple(sorted(tuple(dict.fromkeys(banners[-1] + banners[-2]))))
                    # Remove the new banner since it's been merged into the previous one.
                    del banners[-1]
                    # Check if the newly merged banner can be merged again to the new previous banner.
                    # Don't do this second merge if explicitly marked not to.
                    if len(banners) > 1 and len(set(banners[-2]).intersection(set(banners[-1]))) > 0 and title not in NO_MERGE: # Valentine 2022/Event Info
                        # Remove duplicates from the merged banner and sort it.
                        banners[-2] = tuple(sorted(tuple(dict.fromkeys(banners[-1] + banners[-2]))))
                        # Remove the new banner since it's been merged into the previous one.
                        del banners[-1]
                
                # Keep track of the number of rateup tables that have been parsed.
                cntr += 1

    # In older pages, the rateup servants are not in a wikitable, but are instead in links.
    # If the page is marked as priority, no need to look for keywords and parse servants regardless.
    if not (CURRENT_REGION == "JP" and CURRENT_YEAR >= 2021) and not (CURRENT_REGION == "NA" and CURRENT_YEAR >= 2023):
        if not banners and title in PRIORITY_PAGES:
            # Get all the links in the page.
            links = wikicode.filter_wikilinks()
            # Initialize the list of rateup servants.
            rateup_servants = []

            # Check every link to see if it is a valid servant name.
            for link in links:
                # Fix any errors in the servant name
                name = correct_name(str(link.title).strip())
                # Add the servant name to the list of rateup servants if it is a valid servant name.
                if name in SERVANT_NAMES:
                    rateup_servants.append(name)

            # If rateup servants were found...
            if rateup_servants:
                # Sort and dedupe the servants.
                rateup_servants.sort()
                rateup_servants = tuple(dict.fromkeys(rateup_servants))
                # Append the rateup to the start of the banners list.
                banners.insert(0, rateup_servants)
        # If the page is not marked as priority, look for keywords and parse servants if found.
        elif not banners and title not in PRIORITY_PAGES:
            links = []
            # Get the indexes that indicate sections of the text to parse and sections to skip.
            splits = search_text(text)
            
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

                # Initialize the list of rateup servants.
                rateup_servants = []
                # Check every link to see if it is a valid servant name and add it to the list of rateup servants if it is.
                for link in links:
                    # Fix any errors in the servant name
                    name = correct_name(str(link.title).strip())
                    # Add the servant name to the list of rateup servants if it is a valid servant name.
                    if name in SERVANT_NAMES:
                        rateup_servants.append(name)

                # If rateup servants were found...
                if rateup_servants:
                    # Sort and dedupe the servants.
                    rateup_servants.sort()
                    rateup_servants = tuple(dict.fromkeys(rateup_servants))
                    # Append the rateup to the start of the banners list (since the page is parsed backwards).
                    banners.insert(0, rateup_servants)

    # Dedupe the rateups.
    banners = list(dict.fromkeys(banners))

    # Date if it has event headers
    templates = wikicode.filter_templates()
    if len(templates) > 0 and templates[0].name.strip() == "EventHeaderJP":
        start_date = templates[0].get("start").value.strip()
        try:
            end_date = templates[0].get("end").value.strip()
        except ValueError:
            end_date = start_date
        if not end_date:
            end_date = start_date

        event_date = date_parser(start_date, end_date)
    # Date if it has old-style headers
    else:
        # Get the lines from text
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if i >= 4:
                break
            if "Duration" in line and title not in SKIP_DURATION_PARSE:
                # Remove "'''" from line
                line = re.sub(r"'''", '', line)
                date_split = line.split(": ")[1].split("~")
                if len(date_split) == 1:
                    date_split = date_split[0].split("-")
                if len(date_split) == 1:
                    date_split = date_split[0].split("～")
                if not date_split[1].strip():
                    date_split[1] = date_split[0]
                event_date = date_parser(date_split[0], date_split[1])
                break

    # Create a list of dates the same size as the list of banners.
    dates = [event_date] * len(banners)

    subpage_title = title
    if any(keyword in title for keyword in SUBPAGE_TITLE_REMOVE):
        subpage_title = re.sub(r'(?<!Fate)\/.*', '', title)
    elif any(keyword in title for keyword in SUBPAGE_TITLE_REPLACE):
        subpage_title = re.sub(r'(?<!Fate)\/', ' ', title)
    rateup_titles = [subpage_title] * len(banners)

    # Finds date on pages with multiple summoning campaigns on different tabs
    matches = re.findall(r'(.*Summo.*(?:\w|\)))=\n*((?:\[\[|{{|{\|).*)\n\n*(?:.*Duration.*?(?: |\'|:)([A-Z].*))?', text)

    i = 0
    for match in matches:
        if "Lucky" not in match[0] and "Guaranteed" not in match[0] and title not in FAKE_BANNERS and "tabber" not in match[1]:
            try:
                rateup_titles[i] = f'{subpage_title} {match[0].strip()}'
            except:
                pass

            if match[2]:
                dates[i] = match[2]

            i += 1

    # Save the date of page creation with the summoning campaign.
    if parent:
        try:
            banner_dict[parent][0].extend(dates)
            banner_dict[parent][1].extend(banners)
            banner_dict[parent][2].extend(rateup_titles)
        except KeyError:
            banner_dict[parent] = [dates, banners, rateup_titles]
    else:
        banner_dict[title] = [dates, banners, rateup_titles]

def pre_release_remove(banner_dict):
    # Delete any existing precampaigns
    vals = list(banner_dict.values())
    try:
        for i in range(-2, -5, -1):
            mark_for_del = False
            for rateup in vals[i][1]:
                if rateup in vals[-1][1]:
                    # Transfer date and rateup titles over
                    dest_index = vals[-1][1].index(rateup)
                    src_index = vals[i][1].index(rateup)
                    vals[-1][0][dest_index] = vals[i][0][src_index]
                    vals[-1][2][dest_index] = vals[i][2][src_index]
                    mark_for_del = True
            # Delete that element
            if mark_for_del == True:
                del banner_dict[list(banner_dict.keys())[i]]
                i -= 1
    except IndexError:
        pass

def post_release_remove(banner_dict):
    # Delete any existing precampaigns
    vals = list(banner_dict.values())
    try:
        mark_for_del = False
        for i in range(-2, -5, -1):
            for rateup in vals[-1][1]:
                if rateup in vals[i][1]:
                    # Delete that element
                    dest_index = vals[i][1].index(rateup)
                    src_index = vals[-1][1].index(rateup)
                    vals[i][0][dest_index] = vals[-1][0][src_index]
                    vals[i][2][dest_index] = vals[-1][2][src_index]
                    mark_for_del = True
    except IndexError:
        pass
    # Delete that element
    if mark_for_del == True:
        del banner_dict[list(banner_dict.keys())[-1]]

def pre_release_merge(banner_dict):
    # Delete any existing precampaigns
    keys = list(banner_dict.keys())
    vals = list(banner_dict.values())
    try:
        for i in range(-2, -5, -1):
            # Merge pre-releases not merged on the wiki
            pre_release_parent = keys[i].split("Pre-Release")[0].strip()
            if pre_release_parent == keys[-1]:
                vals[-1][0].extend(vals[i][0])
                vals[-1][1].extend(vals[i][1])
                vals[-1][2].extend(vals[i][2])
                del banner_dict[list(banner_dict.keys())[i]]
                i -= 1
    except IndexError:
        pass

def rec_check_subpages(banner_dict, event_page, date, parent_title):
    event_text = event_page.text
    event_wikicode = mwparserfromhell.parse(event_text)
    event_templates = event_wikicode.filter_templates()
    for event_template in event_templates:
        event_subpage = str(event_template.name)
        # If the event template contains the phrase "Summoning Campaign", parse it.
        if any(keyword in event_subpage for keyword in SUMMON_SUBPAGE):
            summon_name = event_subpage[1:]
            summon_page = pywikibot.Page(SITE, summon_name)
            parse(banner_dict, summon_page, date, parent_title)

            # Check another level of subpages
            rec_check_subpages(banner_dict, summon_page, date, parent_title)
            pre_release_remove(banner_dict)

# Parse test pages
def parse_test():
    page = pywikibot.Page(SITE, "Event List/2021 Events")
    # Get the title of the page
    print(page.title())
    print()
    text = page.text
    wikicode = mwparserfromhell.parse(text)

    events = wikicode.filter_wikilinks()
    events = [x for x in events if not x.startswith("[[File:") and not x.startswith("[[Category:") and not x.startswith("[[#")]
    events = [x.title for x in events]

    # events = wikicode.filter_templates()
    # events = [x.get("event").value.strip() for x in events]

    events.reverse()

    for event in events:
        print(event)

# Parse events
def parse_event_lists():
    global CURRENT_YEAR
    global CURRENT_REGION

    # Parse event lists
    for event_list in EVENT_LISTS:
        CURRENT_YEAR = int(event_list.split('/')[1][:4])
        CURRENT_REGION = "NA" if "US" in event_list else "JP"
        banner_dict = BANNER_DICT_NA if CURRENT_REGION == "NA" else BANNER_DICT_JP
        page = pywikibot.Page(SITE, event_list)
        print(f"Parsing {page.title()}...")
        text = page.text

        # Get the date of each event
        date_list = []
        # Loop through each line in page.text.
        for line in text.splitlines():
            if CURRENT_YEAR >= 2023:
                break
            # If the line contains a month, save it.
            if any(month in line for month in MONTHS) and \
                not line.endswith("=") and \
                not (page.title() in SKIP_DATES and line in SKIP_DATES[page.title()]) and \
                not "[[" in line:
                # Match ".*\|" and remove anything before it.
                line = re.sub(r'.*\|', '', line)
                date_split = line.split("~")
                date_list.append(date_parser(line, line) if len(date_split) == 1 else date_parser(date_split[0], date_split[1]))

        wikicode = mwparserfromhell.parse(text)
        events = None
        # 2021 and 2022 NA event list uses wikilinks
        if CURRENT_YEAR < 2023:
            events = wikicode.filter_wikilinks()
            # Filter out non-event pages
            events = [x for x in events if not x.startswith("[[File:") and not x.startswith("[[Category:") and not x.startswith("[[#")]
            # Get the title of each event
            events = [str(x.title) for x in events]
        # 2023 NA event list uses templates
        else:
            event_templates = wikicode.filter_templates()
            # Get the title of each event
            events = [x.get("event").value.strip() for x in event_templates]
            starts = [x.get("start").value.strip() for x in event_templates]
            ends = []
            for i, x in enumerate(event_templates):
                try:
                    ends.append(x.get("end").value.strip())
                except ValueError:
                    ends.append(starts[i])
            date_list = [date_parser(starts[i], ends[i]) for i in range(len(starts))]

        # Reverse events and date list
        events.reverse()
        date_list.reverse()
        # Create an OrderedDict where the key is the event name and the value is the date of the event.
        events = OrderedDict(zip(events, date_list))

        # events = ["Valentine 2020"]
        
        # Parse each event
        for event, date in (pbar := tqdm(events.items(), bar_format=BAR_FORMAT)):
            pbar.set_postfix_str(event)
            event_page = pywikibot.Page(SITE, event)
            parse(banner_dict, event_page, date)

            if event_page.title() in INCLUDE_SUBPAGES:
                for subpage in INCLUDE_SUBPAGES[event_page.title()]:
                    summon_page = pywikibot.Page(SITE, subpage)
                    parse(banner_dict, summon_page, date, event_page.title())
                    pre_release_remove(banner_dict)

            # Parse any summoning campaign subpages
            rec_check_subpages(banner_dict, event_page, date, event_page.title())

            post_release_remove(banner_dict)
            pre_release_merge(banner_dict)

# Remove banners with no rateups.
def remove_empty(banner_dict):
    # Delete banners with empty rateups.
    print('Cleaning up empty rateups...')
    for banner in list(banner_dict):
        if not banner_dict[banner][1]:
            del banner_dict[banner]

# If TESTING is 1, parse the test pages. Otherwise, parse the Summoning Campaign category.
if TESTING == 1:
    parse_test()
else:
    parse_event_lists()

# Remove banners with no rateups.
remove_empty(BANNER_DICT_JP)
remove_empty(BANNER_DICT_NA)

# Sort the banners by date.
print("Sorting by date...")
banner_list_jp = []
for banner in BANNER_DICT_JP:
    banner_list_jp.append({
        'name': banner,
        'rateup_names' : BANNER_DICT_JP[banner][2],
        'dates': BANNER_DICT_JP[banner][0],
        'rateups': BANNER_DICT_JP[banner][1]
    })
banner_list_na = []
for banner in BANNER_DICT_NA:
    banner_list_na.append({
        'name': banner,
        'rateup_names' : BANNER_DICT_NA[banner][2],
        'dates': BANNER_DICT_NA[banner][0],
        'rateups': BANNER_DICT_NA[banner][1]
    })

# Save the banner list to a JSON file.
print("Saving to JSON file...")

# Filenames for the old and new JSON files.
FILE_OLD_JP = "summon_data_test_old.json" if TESTING == 1 else "summon_data_old.json"
FILE_NEW_JP = "summon_data_test.json" if TESTING == 1 else "summon_data.json"
FILE_OLD_NA = "summon_data_na_test_old.json" if TESTING == 1 else "summon_data_na_old_na.json"
FILE_NEW_NA = "summon_data_na_test.json" if TESTING == 1 else "summon_data_na.json"

# Save the old version of the JSON file for diff comparison.
shutil.copy(os.path.join(DIR_PATH, FILE_NEW_JP), os.path.join(DIR_PATH, FILE_OLD_JP))
shutil.copy(os.path.join(DIR_PATH, FILE_NEW_NA), os.path.join(DIR_PATH, FILE_OLD_NA))

# Create the new version of the JSON file from the banner list.
json_obj = jsons.dump(banner_list_jp)
with open(os.path.join(DIR_PATH, FILE_NEW_JP), 'w') as f:
    f.write(json.dumps(json_obj, indent=2).encode().decode('unicode-escape'))
json_obj = jsons.dump(banner_list_na)
with open(os.path.join(DIR_PATH, FILE_NEW_NA), 'w') as f:
    f.write(json.dumps(json_obj, indent=2).encode().decode('unicode-escape'))

# Write the diff between the old and new banner list JSON to a file.
with open(os.path.join(DIR_PATH, FILE_NEW_JP), 'r') as f1:
    with open(os.path.join(DIR_PATH, FILE_OLD_JP), 'r') as f2:
        diff = difflib.unified_diff(f2.readlines(), f1.readlines())
        with open(os.path.join(DIR_PATH, 'diff_jp.txt'), 'w') as f3:
            f3.writelines(diff)
with open(os.path.join(DIR_PATH, FILE_NEW_NA), 'r') as f1:
    with open(os.path.join(DIR_PATH, FILE_OLD_NA), 'r') as f2:
        diff = difflib.unified_diff(f2.readlines(), f1.readlines())
        with open(os.path.join(DIR_PATH, 'diff_na.txt'), 'w') as f3:
            f3.writelines(diff)
