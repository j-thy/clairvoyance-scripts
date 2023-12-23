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

# Read in test parameter from command line.
TESTING = 0
if len(sys.argv) > 1:
    TESTING = int(sys.argv[1])

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
NA_EVENT_LISTS = {
    "Event List/2015 Events" : 0,
    "Event List/2016 Events" : 0,
    "Event List/2017 Events" : 0,
    "Event List/2018 Events" : 0,
    "Event List/2019 Events" : 0,
    "Event List/2020 Events" : 0,
    "Event List/2021 Events" : 0,
    "Event List/2022 Events" : 0,
    "Event List/2023 Events" : 1,
    "Event List (US)/2017 Events" : 0,
    "Event List (US)/2018 Events" : 0,
    "Event List (US)/2019 Events" : 0,
    "Event List (US)/2020 Events" : 0,
    "Event List (US)/2021 Events" : 0,
    "Event List (US)/2022 Events" : 0,
    "Event List (US)/2023 Events" : 1
}

# Get the FGO wiki site.
SITE = pywikibot.Site()

# Import the servant data and get the names of all the servants.
servant_data = None
with open(os.path.join(os.path.dirname(__file__), 'servant_data.json')) as f:
    servant_data = jsons.loads(f.read())
servant_names = set([servant_data[servant]['name'] for servant in servant_data])

# Initialize the summoning campaign and event dictionaries.
BANNER_DICT = OrderedDict()
EVENT_DICT = {}
EVENT_TITLES = ()
CURRENT_YEAR = 0
CURRENT_REGION = ""

# Finds indexes of matching keywords in order to breaks link-style pages into chunks, each ideally with a rateup.
def search_text(text):
    splits = {}

    # Find index of keywords that indicate a rateup coming after. Mark it to be preserved.
    for string in LINK_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            if TESTING == 1:
                print(string)
            splits[match.start()] = True
    
    # Find index of keywords that are before sections causing false positives. Mark it to be removed.
    for string in REMOVE_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            if TESTING == 1:
                print(string)
            splits[match.start()] = False
    
    # Sort the indexes of the splits and return it.
    splits = {k: v for k, v in sorted(splits.items(), key=lambda item: item[0], reverse=True)}
    return splits

# Fix any errors in the servant name.
def correct_name(text):
    if text in NAME_FIXES:
        return NAME_FIXES[text]
    return text

# Parse a wiki page
def parse(page, parent=None):
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
    # print(text)

    # Apply any priority text removals, removing the match and everything after it.
    for string in PRIORITY_REMOVE_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            text = text[:match.start()]

    # Parse the text
    wikicode = mwparserfromhell.parse(text)
    if TESTING == 1:
        print(text)

    # Initialize the list of rateups.
    banners = []

    # Find and parse the rateup servants wikitable, unless the page is explicitly marked to skip this.
    if title not in SKIP_TABLE_PARSE_PAGES:
        # Get all the tags in the page, any of which may contain the rateup servants wikitable.
        tags = wikicode.filter_tags()
        # print(tags)

        cntr = 0
        # Find any tags containing the rateup servants wikitable.
        for tag in tags:
            # print(tag)
            # print("\n\n")

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
                if name in servant_names:
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

    # print(banners)
    # print(text)

    # In older pages, the rateup servants are not in a wikitable, but are instead in links.
    # If the page is marked as priority, no need to look for keywords and parse servants regardless.
    if not banners and title in PRIORITY_PAGES and not (CURRENT_REGION == "JP" and CURRENT_YEAR >= 2022):
        # Get all the links in the page.
        links = wikicode.filter_wikilinks()
        # Initialize the list of rateup servants.
        rateup_servants = []

        # Check every link to see if it is a valid servant name.
        for link in links:
            # print(link.title)
            # Fix any errors in the servant name
            name = correct_name(str(link.title).strip())
            # Add the servant name to the list of rateup servants if it is a valid servant name.
            if name in servant_names:
                rateup_servants.append(name)

        # If rateup servants were found...
        if rateup_servants:
            # Sort and dedupe the servants.
            rateup_servants.sort()
            rateup_servants = tuple(dict.fromkeys(rateup_servants))
            # Append the rateup to the start of the banners list.
            banners.insert(0, rateup_servants)
    # If the page is not marked as priority, look for keywords and parse servants if found.
    elif not banners and title not in PRIORITY_PAGES and not (CURRENT_REGION == "JP" and CURRENT_YEAR >= 2022):
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
            # print(links)

            # Initialize the list of rateup servants.
            rateup_servants = []
            # Check every link to see if it is a valid servant name and add it to the list of rateup servants if it is.
            for link in links:
                # print(link.title)
                # Fix any errors in the servant name
                name = correct_name(str(link.title).strip())
                # Add the servant name to the list of rateup servants if it is a valid servant name.
                if name in servant_names:
                    rateup_servants.append(name)

            # If rateup servants were found...
            if rateup_servants:
                # Sort and dedupe the servants.
                rateup_servants.sort()
                rateup_servants = tuple(dict.fromkeys(rateup_servants))
                # Append the rateup to the start of the banners list (since the page is parsed backwards).
                banners.insert(0, rateup_servants)

    # print(banners)

    # Dedupe the rateups.
    banners = list(dict.fromkeys(banners))
    # print(banners)

    # Save the date of page creation with the summoning campaign.
    if parent:
        try:
            BANNER_DICT[parent][1].extend(banners)
        except KeyError:
            BANNER_DICT[parent] = [page.oldest_revision.timestamp, banners]
    else:
        BANNER_DICT[title] = [page.oldest_revision.timestamp, banners]
    # print(banners)

# Parse test pages
def parse_test():
    # Parse each event
    for event in (pbar := tqdm(TEST_PAGES, bar_format=BAR_FORMAT)):
        pbar.set_postfix_str(event)
        event_page = pywikibot.Page(SITE, event)
        parse(event_page)
        # print(f'1: Parsing {event_page.title()}: {BANNER_DICT}')

        if event_page.title() in INCLUDE_SUBPAGES:
            for subpage in INCLUDE_SUBPAGES[event_page.title()]:
                summon_page = pywikibot.Page(SITE, subpage)
                parse(summon_page, event_page.title())
                pre_release_remove()

        # Parse any summoning campaign subpages
        rec_check_subpages(event_page, event_page.title())

        post_release_remove()
        # print(f'2: {BANNER_DICT}')

def pre_release_remove():
    # Delete any existing precampaigns
    vals = list(BANNER_DICT.values())
    try:
        for i in range(-2, -5, -1):
            # print(f'{list(BANNER_DICT.keys())[i]} ? {list(BANNER_DICT.keys())[-1]}')
            for rateup in vals[i][1]:
                if rateup in vals[-1][1]:
                    # Delete that element
                    del BANNER_DICT[list(BANNER_DICT.keys())[i]]
                    break
    except IndexError:
        pass

def post_release_remove():
    # Delete any existing precampaigns
    vals = list(BANNER_DICT.values())
    try:
        for i in range(-2, -5, -1):
            for rateup in vals[-1][1]:
                if rateup in vals[i][1]:
                    # Delete that element
                    del BANNER_DICT[list(BANNER_DICT.keys())[-1]]
                    break
    except IndexError:
        pass

def rec_check_subpages(event_page, parent_title):
    event_text = event_page.text
    event_wikicode = mwparserfromhell.parse(event_text)
    event_templates = event_wikicode.filter_templates()
    for event_template in event_templates:
        event_subpage = str(event_template.name)
        # If the event template contains the phrase "Summoning Campaign", parse it.
        if any(keyword in event_subpage for keyword in SUMMON_SUBPAGE):
            summon_name = event_subpage[1:]
            summon_page = pywikibot.Page(SITE, summon_name)
            parse(summon_page, parent_title)
            # print(f'R: Parsing {summon_page.title()}: {BANNER_DICT}')

            # Check another level of subpages
            rec_check_subpages(summon_page, parent_title)
            pre_release_remove()

# Parse events
def parse_event_lists():
    global CURRENT_YEAR
    global CURRENT_REGION

    # Parse event lists
    for event_list, type_parse in NA_EVENT_LISTS.items():
        CURRENT_YEAR = int(event_list.split('/')[1][:4])
        CURRENT_REGION = "NA" if "US" in event_list else "JP"
        page = pywikibot.Page(SITE, event_list)
        print(f"Parsing {page.title()}...")
        text = page.text
        wikicode = mwparserfromhell.parse(text)
        events = None
        # 2021 and 2022 NA event list uses wikilinks
        if type_parse == 0:
            events = wikicode.filter_wikilinks()
            # Filter out non-event pages
            events = [x for x in events if not x.startswith("[[File:") and not x.startswith("[[Category:") and not x.startswith("[[#")]
            # Get the title of each event
            events = [x.title for x in events]
        # 2023 NA event list uses templates
        else:
            events = wikicode.filter_templates()
            # Get the title of each event
            events = [x.get("event").value.strip() for x in events]
        
        # Reverse events
        events.reverse()

        # events = ["Valentine 2020"]
        
        # Parse each event
        for event in (pbar := tqdm(events, bar_format=BAR_FORMAT)):
            pbar.set_postfix_str(event)
            event_page = pywikibot.Page(SITE, event)
            parse(event_page)
            # print(f'1: Parsing {event_page.title()}: {BANNER_DICT}')

            if event_page.title() in INCLUDE_SUBPAGES:
                for subpage in INCLUDE_SUBPAGES[event_page.title()]:
                    summon_page = pywikibot.Page(SITE, subpage)
                    parse(summon_page, event_page.title())
                    # print(f'I: Parsing {summon_page.title()}: {BANNER_DICT}')
                    pre_release_remove()

            # Parse any summoning campaign subpages
            rec_check_subpages(event_page, event_page.title())

            post_release_remove()
            # print(f'2: {BANNER_DICT}')

def parse_event_list_test():
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

# Remove banners with no rateups.
def remove_empty():
    # Delete banners with empty rateups.
    print('Cleaning up empty rateups...')
    for banner in list(BANNER_DICT):
        if not BANNER_DICT[banner][1]:
            del BANNER_DICT[banner]

# parse_event_list_test()
# sys.exit(0)

# If TESTING is 1, parse the test pages. Otherwise, parse the Summoning Campaign category.
if TESTING == 1:
    parse_test()
else:
    parse_event_lists()

# Remove banners with no rateups.
remove_empty()

# Sort the banners by date.
print("Sorting by date...")
banner_list = []
for banner in BANNER_DICT:
    banner_list.append({
        'name': banner,
        'date': BANNER_DICT[banner][0],
        'rateups': BANNER_DICT[banner][1]
    })
banner_list.sort(key=lambda x: x['date'])

# Save the banner list to a JSON file.
print("Saving to JSON file...")
# Save the old version of the JSON file for diff comparison.
FILE_OLD = "summon_data_test_old.json" if TESTING == 1 else "summon_data_old.json"
FILE_NEW = "summon_data_test.json" if TESTING == 1 else "summon_data.json"
shutil.copy(os.path.join(os.path.dirname(__file__), FILE_NEW), os.path.join(os.path.dirname(__file__), FILE_OLD))

# Create the new version of the JSON file from the banner list.
json_obj = jsons.dump(banner_list)
with open(os.path.join(os.path.dirname(__file__), FILE_NEW), 'w') as f:
    f.write(json.dumps(json_obj, indent=2))

# Write the diff between the old and new banner list JSON to a file.
with open(os.path.join(os.path.dirname(__file__), FILE_NEW), 'r') as f1:
    with open(os.path.join(os.path.dirname(__file__), FILE_OLD), 'r') as f2:
        diff = difflib.unified_diff(f2.readlines(), f1.readlines())
        with open(os.path.join(os.path.dirname(__file__), 'diff.txt'), 'w') as f3:
            f3.writelines(diff)
