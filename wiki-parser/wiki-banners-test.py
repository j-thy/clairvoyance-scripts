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

# TODO: Fix FGO Summer 2018 Event Revival (US)/Summoning Campaign

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
    "New Information="
)

# Pages that should not be parsed nor merged into.
FULL_EXCLUDE_PAGES = (
    "Jack Campaign",
    "Mysterious Heroine X Pick Up",
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
    "The Antiquated Spider Nostalgically Spins Its Thread",
    "The Antiquated Spider Nostalgically Spins Its Thread/Main Info",
    "Aeaean Spring Breeze",
    "Aeaean Spring Breeze/Main Info",
    "Slapstick Museum",
    "Slapstick Museum/Main Info",
    "Fate/Apocrypha Event Pre-Release Campaign (US)/Rate Up Schedule",
)

# Pages that should not be parsed but can be merged into.
EXCLUDE_PARSE_PAGES = (
    "Valentine 2020/Main Info",
    "Valentine 2020",
    "Traum Chapter Release",
)

# Pages with wikitables that can generate false positives so table-style parsing should be skipped.
SKIP_TABLE_PARSE_PAGES = (
    "Prisma Codes Collaboration Event (US)/Summoning Campaign",
)

# Pages not in the Summoning Campaign category but has rateups that should be parsed.
INCLUDE_PAGES = (
    "London Chapter Release",
    "Babylonia Chapter Release",
    "Chaldea Boys Collection 2016 Re-Run",
    "Chaldea Boys Collection 2017",
    "Agartha Chapter Release",
    "Shimosa Chapter Release",
    "Apocrypha/Inheritance of Glory/Main Info",
    "Halloween 2018/Event Info",
    "Lord El-Melloi II Case Files Collaboration Pre-campaign",
    "Fate/Grand Order ～7th Anniversary～ Summoning Campaign",
    "Fate/Grand Order ～7th Anniversary～ Daily Summoning Campaign",
    "Halloween 2018 Rerun/Main Info",
    "Christmas 2019 Re-Run/Event Info",
    "Imaginary Scramble/Event Info",
    "Babylonia Chapter Release (US)", # 2018
    "Solomon Chapter Release (US)", # 2018
    "Fate/Stay Night Heaven's Feel II Blu-ray Release Commemorative Campaign (US)", # 2019
    "Murder at the Kogetsukan (US)", # 2020
    "Fate/Stay Night Heaven's Feel III Theatrical Release Commemorative Campaign (US)", #2020
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

# Pages that should not be included in the list of events.
EVENT_PAGES_REMOVE = (
    "Event List",
    "Event Items",
)

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
}

# Test pages to parse.
TEST_PAGES = (
    "Fate/Apocrypha Collaboration Event Revival (US)/Summoning Campaign",
)

# TODO: Used in fix for later US events not being in Summoning Campaign category.
# If it is 0, parse wikinlinks
# If it is 1, parse templates
NA_EVENT_LISTS = {
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
BANNER_DICT = {}
EVENT_DICT = {}
EVENT_TITLES = ()

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
def parse(page):
    # Get the title of the page
    title = page.title()

    # Do not parse pages that are marked no-parse/no-merge or no-parse/mergeable or title starts with "User blog:"
    if title in FULL_EXCLUDE_PAGES or title in EXCLUDE_PARSE_PAGES or title.startswith("User blog:"):
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
    if not banners and title in PRIORITY_PAGES:
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
    BANNER_DICT[title] = [page.oldest_revision.timestamp, banners]
    # print(banners)

# Parse test pages
def parse_test():
    global EVENT_TITLES

    # Create a list of all the event titles.
    event_category = pywikibot.Category(SITE, "Event")
    EVENT_TITLES = tuple([x.title() for x in event_category.articles()])
    EVENT_TITLES = tuple([x for x in EVENT_TITLES if x not in TEST_PAGES and not any([event_page in x for event_page in EVENT_PAGES_REMOVE])])

    # Parse each test page.
    for page_name in TEST_PAGES:
        page = pywikibot.Page(SITE, page_name)
        parse(page)

# Parse recent NA events
def parse_na():
    # Parse more recent NA event lists
    for event_list, type_parse in NA_EVENT_LISTS.items():
        page = pywikibot.Page(SITE, event_list)
        print(f"Parsing {page.title()}...")
        text = page.text
        wikicode = mwparserfromhell.parse(text)
        events = None
        # 2021 and 2022 NA event list uses wikilinks
        if type_parse == 0:
            events = wikicode.filter_wikilinks()
            # Filter out non-event pages
            events = [x for x in events if not x.startswith("[[File:") and not x.startswith("[[Category:")]
            # Get the title of each event
            events = [x.title for x in events]
        # 2023 NA event list uses templates
        else:
            events = wikicode.filter_templates()
            # Get the title of each event
            events = [x.get("event").value.strip() for x in events]
        
        # Parse each event
        for event in (pbar := tqdm(events, bar_format=BAR_FORMAT)):
            pbar.set_postfix_str(event)
            event_page = pywikibot.Page(SITE, event)
            parse(event_page)

            # Parse any summoning campaign subpages
            event_text = event_page.text
            event_wikicode = mwparserfromhell.parse(event_text)
            event_templates = event_wikicode.filter_templates()
            for event_template in event_templates:
                event_subpage = str(event_template.name)
                # If the event template contains the phrase "Summoning Campaign", parse it.
                if "Summoning Campaign" in event_subpage or "Summoning_Campaign" in event_subpage:
                    # Slice the first character off the name of the summoning campaign.
                    summon_name = event_subpage[1:]
                    summon_page = pywikibot.Page(SITE, summon_name)
                    parse(summon_page)

def parse_na_test():
    page = pywikibot.Page(SITE, "Christmas 2022 Event (US)")
    # Get the title of the page
    print(page.title())
    print()
    text = page.text
    wikicode = mwparserfromhell.parse(text)
    tags = wikicode.filter_templates()
    for tag in tags:
        print(tag.name)

# Parse the Summoning Campaign category
def parse_category():
    global EVENT_TITLES

    print("Fetching wiki pages...")
    # Get pages in the Summoning Campaign, Arcade, Event, and Chapter Release Campaign categories.
    summoning_category = pywikibot.Category(SITE, "Summoning Campaign")
    arcade_category = pywikibot.Category(SITE, "Arcade")
    event_category = pywikibot.Category(SITE, "Event")
    campaign_category = pywikibot.Category(SITE, "Chapter Release Campaign")

    # Get the titles of the pages in the Arcade and Summoning Campaign categories.
    arcade_titles = tuple([x.title() for x in arcade_category.articles()])
    summoning_titles = tuple([x.title() for x in summoning_category.articles()])

    # Get the number of pages in the Summoning Campaign category.
    summoning_length = len(list(summoning_category.articles()))

    print("Fetching event and campaign titles...")
    # Create a list of all the event titles but exclude Arcade, Summoning Campaign, excluded pages, and included pages.
    EVENT_TITLES = tuple([x.title() for x in event_category.articles()])
    EVENT_TITLES = tuple([x for x in EVENT_TITLES if x not in arcade_titles and x not in summoning_titles and x not in FULL_EXCLUDE_PAGES and x not in INCLUDE_PAGES and not any([event_page in x for event_page in EVENT_PAGES_REMOVE])])

    # Create a list of all the campaign titles but exclude Arcade, Summoning Campaign, excluded pages, and included pages.
    campaign_titles = tuple([x.title() for x in campaign_category.articles()])
    campaign_titles = tuple([x for x in campaign_titles if x not in arcade_titles and x not in summoning_titles and x not in FULL_EXCLUDE_PAGES and x not in INCLUDE_PAGES and x not in EVENT_TITLES])

    # Add the campaign titles to the event titles along with the no-parse/mergeable pages.
    # These are events that can be merged into but not parsed.
    EVENT_TITLES = EVENT_TITLES + campaign_titles + EXCLUDE_PARSE_PAGES

    print("Parsing summoning campaigns...")
    # Parse each summoning campaign page, excluding the pages in the Arcade category.
    for page in (pbar := tqdm(summoning_category.articles(), total=summoning_length, bar_format=BAR_FORMAT)):
        title = page.title()
        pbar.set_postfix_str(title)
        if title in arcade_titles:
            continue
        parse(page)
    
    print("Parsing included pages...")
    # Parse each explicitly included page.
    for page_name in (pbar := tqdm(INCLUDE_PAGES, bar_format=BAR_FORMAT)):
        pbar.set_postfix_str(page_name)
        page = pywikibot.Page(SITE, page_name)
        parse(page)

# Parse a single page.
def parse_page(page_name):
    page = pywikibot.Page(SITE, page_name)
    parse(page)

# Goes up the chain of template references to find the original template/banner.
def rec_get_ref(original_banner, banner, visited): # Test on 3M Downloads Campaign and 13 Bespeckled
    # print(f'Original Banner: {original_banner}, Banner: {banner}')

    # Parse the current page.
    page = pywikibot.Page(SITE, banner)
    # Get the number of pages that reference the current page that are summoning campaigns or events.
    num_refs = len([x for x in list(page.getReferences(only_template_inclusion=True)) if x.title() in BANNER_DICT or x.title() in EVENT_TITLES])
    # print(f'Found {num_refs} references for {banner}')
    # print(visited)

    # If no references are found for the original banner...
    if num_refs == 0 and banner == original_banner:
        # print(f'In first if condition for {banner}')
        # print(f'No references found for {banner}.')

        # If you can split the banner name by / and the name on the left is a valid summoning campagin, then it's a subpage.
        if '/' in banner and banner.split('/')[0] in BANNER_DICT:
            # Add its rateups to the summoning campaign indicated by the name to the left of the /.
            for rateup in BANNER_DICT[banner][1]:
                if rateup not in BANNER_DICT[banner.split('/')[0]][1]:
                    BANNER_DICT[banner.split('/')[0]][1].append(rateup)
            # Mark the subpage for deletion.
            return True
        # If you can split the banner name by / and the name on the left is a valid event that already holds rateups, then it's a subpage.
        elif '/' in banner and banner.split('/')[0] in EVENT_DICT:
            # Add its rateups to the event indicated by the name to the left of the /.
            for rateup in BANNER_DICT[banner][1]:
                if rateup not in EVENT_DICT[banner.split('/')[0]][1]:
                    EVENT_DICT[banner.split('/')[0]][1].append(rateup)
            # Mark the subpage for deletion.
            return True
        # If you can split the banner name by / and the name on the left is a valid event that hasn't held rateups yet, then it's a subpage.
        elif '/' in banner and banner.split('/')[0] in EVENT_TITLES:
            # Create a new entry for the event and add the subpage's rateups to it.
            EVENT_DICT[banner.split('/')[0]] = [BANNER_DICT[banner][0], BANNER_DICT[banner][1]]
            # Mark the subpage for deletion.
            return True
        # No subpage found.
        else:
            # Don't mark the original banner for deletion.
            return False
    # If no references are found at the current banner (but references were found for previous banners),
    # Or if the current banner has already been visited...
    elif num_refs == 0 or banner in visited:
        # print(f'In second if condition for {banner}')
        # print(f'Merging {banner} into {original_banner}...')

        # Merge the original banner's rateups into the current summoning campaign.
        if banner in BANNER_DICT:
            for rateup in BANNER_DICT[original_banner][1]:
                if rateup not in BANNER_DICT[banner][1]:
                    BANNER_DICT[banner][1].append(rateup)
        # Merge the original banner's rateups into the current event.
        elif banner in EVENT_DICT:
            for rateup in BANNER_DICT[original_banner][1]:
                if rateup not in EVENT_DICT[banner][1]:
                    EVENT_DICT[banner][1].append(rateup)
        # Assign the original banner's rateups into the current event (if it has no rateups yet).
        elif banner in EVENT_TITLES:
            EVENT_DICT[banner] = [BANNER_DICT[original_banner][0], BANNER_DICT[original_banner][1]]
        # Mark the original banner for deletion.
        return True
    # If references are found at the current banner...
    else:
        # print(f'In else condition for {banner}')
        retval = False

        # Recursively check the pages that reference the current page.
        for reference in page.getReferences(only_template_inclusion=True):
            # print(f'Going to {reference.title()}...')
            # Only recurse into the page if it's a summoning campaign or event.
            if reference.title() in BANNER_DICT or reference.title() in EVENT_TITLES:
                # print(f'Entering {reference.title()}...')
                # Add the current banner to the list of visited banners before recursing.
                retval = rec_get_ref(original_banner, reference.title(), visited + (banner,))
        # If the original banner was merged into any reference, mark the original banner for deletion.
        return retval

# Merge banners that are subpages of other banners/events.
def cleanup():
    print("Merging banners...")
    # Check each banner and merge them up to other campaigns and events that reference them.
    for banner in (pbar := tqdm(list(BANNER_DICT), bar_format=BAR_FORMAT)):
        pbar.set_postfix_str(banner)
        ref_exists = rec_get_ref(banner, banner, ())
        # print(ref_exists)

        # If the original banner was merged into any reference, delete the original banner.
        if ref_exists:
            del BANNER_DICT[banner]

# Remove banners with no rateups.
def remove_empty():
    # Delete banners with empty rateups.
    print('Cleaning up empty rateups...')
    for banner in list(BANNER_DICT):
        if not BANNER_DICT[banner][1]:
            del BANNER_DICT[banner]

# Test function to see what pages reference a page.
def cleanup_test():
    page = pywikibot.Page(SITE, "FGO x FGO Arcade Collaboration Summoning Campaign 1")
    print(f'Size of {page.title()}: {len(list(page.getReferences(with_template_inclusion=True, follow_redirects=True)))}')
    for reference in page.getReferences():
        print(reference.title())
        page1 = pywikibot.Page(SITE, reference.title())
        # for reference1 in page1.getReferences():
        #     print(f'  {reference1.title()}')
        #     page2 = pywikibot.Page(SITE, reference1.title())
        #     for reference2 in page2.getReferences():
        #         print(f'    {reference2.title()}')
        #         page3 = pywikibot.Page(SITE, reference2.title())
        #         for reference3 in page3.getReferences():
        #             print(f'      {reference3.title()}')

# parse_na_test()

# sys.exit(0)

# If TESTING is 1, parse the test pages. Otherwise, parse the Summoning Campaign category.
if TESTING == 1:
    parse_test()
else:
    parse_category()

parse_na()

# Merge and delete banners that are subpages of other banners/events.
cleanup()

# Merge list of events with rateups into list of summoning campaigns with rateups.
BANNER_DICT.update(EVENT_DICT)

# Remove banners with no rateups.
remove_empty()

# cleanup_test()

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
