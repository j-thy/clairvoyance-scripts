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

# TODO: Valentine 2019, remove Nightinggale
# TODO: Fate/Extra CCC Collaboration Event (US), add EMIYA (Alter)

CATEGORY = 'Summoning_Campaign'

# Read in TESTING = from command line using sys.
TESTING = 0
if len(sys.argv) > 1:
    TESTING = int(sys.argv[1])

TABLE_MATCHES = (
    "New Servant",
    "Rate-Up Servants",
    "Rate-Up Limited Servants",
    "Rate-Up Servant",
    "Rate Up Servant",
    "Rate-Up Schedule",
    "All-Time Rate Up",
    "Rate-Up", # New Year Campaign 2018
    "Limited Servants", # S I N Summoning Campaign 2
    "Edmond Dantès]] {{LimitedS}}\n|{{Avenger}}\n|-\n|4{{Star}}\n|{{Gilgamesh (Caster)" # Servant Summer Festival! 2018/Event Info
)

TABLE_MERGE_MATCHES = (
    "Rate-Up Schedule",
    "All-Time Rate Up",
)

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
    "Amakusagacha",
    "Babylonia Summoning Campaign",
    "Rate Up Schedule \(Female-Servants 2\)",
    "Rate Up \(Male-Servants\)",
    "Servant Lineups",
    "Salem Summon 2",
    "Valentine2017 gacha rerun",
    "Anastasia_summon_banner2",
    "■ .*? Downloads Summoning Campaign",
    "NeroFestival2018CampaignUS",
)

PRIORITY_REMOVE_MATCHES = (
    "CBC 2022=",
    "{{Napoléon}} {{Valkyrie}} {{Thomas Edison}}", # WinFes 2018/19 Commemoration Summoning Campaign
    "Craft Essences are now unique per party, allowing Servants in multiple parties to hold different Craft Essences", # London Chapter Release
)

REMOVE_MATCHES = (
    "receive one free",
    "==First Quest==",
    "==Prologue==",
    "==.*?Trial Quest.*?==",
    "Lucky Bag Summoning",
    "Music=",
    "Quest=",
    "Grand Summon",
    "Misc Update=",
)

EXCLUDE_PAGES = (
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
)

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
)

NAME_FIXES = {
    'Attila' : 'Altera', # FGO Summer Festival 2016 ~1st Anniversary~
    "EMIYA (Alter) NA" : "EMIYA (Alter)"
}

RATEUP_FIXES = {
    'S I N Chapter Release' : 'Jing Ke', # S I N Chapter Release
}

PAGE_FIXES = {
    'Class Specific Summoning Campaign (US)' : [r'\|(.*)}}\n\[\[', r'|\1}}\n|}\n[['], # Class Specific Summoning Campaign (US)
}

TEST_PAGES = (
    # "Fuun Karakuri Illya's Castle",
    # "Fuun Karakuri Illya's Castle/Summon",
    "Fuun Karakuri Illya's Castle Summoning Campaign",
    # "Fuun Karakuri Illya's Castle Summoning Campaign 2",
    # "Fuun Karakuri Illya's Castle Summoning Campaign 3",
)

SITE = pywikibot.Site()

servant_data = None
# Import servant_data.json as json.
with open(os.path.join(os.path.dirname(__file__), 'servant_data.json')) as f:
    servant_data = jsons.loads(f.read())

# The json is a dictionary, where every value is also a dictionary. Make a set out of the name field in the dictionary in the value.
servant_names = set([servant_data[servant]['name'] for servant in servant_data])
banner_dict = {}

def search_text(text):
    splits = {}

    for string in LINK_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            if TESTING == 1:
                print(string)
            splits[match.start()] = True
    
    for string in REMOVE_MATCHES:   
        matches = re.finditer(string, text)
        for match in matches:
            if TESTING == 1:
                print(string)
            splits[match.start()] = False
    
    splits = {k: v for k, v in sorted(splits.items(), key=lambda item: item[0], reverse=True)}

    return splits

def correct_name(text):
    if text in NAME_FIXES:
        return NAME_FIXES[text]
    return text

def parse(page, progress=None):
    # Iterate through each servant's page.
    # for i, page in enumerate(category.articles()):
    #     if i > 1:
    #         break
    # Get name of servant
    title = page.title()

    if title in EXCLUDE_PAGES:
        return

    if progress:
        print(f'Parsing {progress}: {title}...')
    else:
        print(f'Parsing {title}...')

    # Parse servant info
    text = page.text
    # Remove HTML comments
    text = re.sub(r'<!--(.|\n)*?-->', '', text)
    if title in PAGE_FIXES:
        text = re.sub(PAGE_FIXES[title][0], PAGE_FIXES[title][1], text)
    # print(text)

    for string in PRIORITY_REMOVE_MATCHES:
        matches = re.finditer(string, text)
        for match in matches:
            text = text[:match.start()]

    wikicode = mwparserfromhell.parse(text)
    if TESTING == 1:
        print(text)

    banners = []

    # Find the template containing the servant details
    tags = wikicode.filter_tags()
    # print(tags)

    # Find the rateups on pages that use tables.
    for tag in tags:
        # print(tag)
        # print("\n\n")
        class_type = None
        try:
            class_type = tag.get("class").value.strip()
        except ValueError:
            pass
        if class_type != 'wikitable' or not any([x in tag for x in TABLE_MATCHES]):
            continue
        # print("test")
        table = mwparserfromhell.parse(tag)
        templates = table.filter_templates()
        try:
            rateup_servants = list(banners.pop()) if any([x in tag for x in TABLE_MERGE_MATCHES]) else [] # Atlantis Chapter Release
        except IndexError:
            rateup_servants = [] # CBC 2016 ~ 2019 Craft Essences Summoning Campaign
        for template in templates:
            name = correct_name(str(template.name))
            if name in servant_names:
                rateup_servants.append(name)
        
        for string in RATEUP_FIXES:
            if string == title:
                rateup_servants.append(RATEUP_FIXES[string])

        if rateup_servants:
            rateup_servants.sort()
            rateup_servants = tuple(dict.fromkeys(rateup_servants))
            banners.append(rateup_servants)

    # print(banners)
    # print(text)
    # If a page that uses wikilinks only
    if not banners:
        links = []
        splits = search_text(text)
        base_text = text
        for key, value in splits.items():
            # Split text into 2 substrings based on the int in split.
            parse_text = base_text[key:]
            base_text = base_text[:key]
            if not value:
                continue
            sub_wikicode = mwparserfromhell.parse(parse_text)
            links = sub_wikicode.filter_wikilinks()
            # print(links)
            rateup_servants = []
            for link in links:
                # print(link.title)
                name = correct_name(str(link.title).strip())
                if name in servant_names:
                    rateup_servants.append(name)

            if rateup_servants:
                rateup_servants.sort()
                rateup_servants = tuple(dict.fromkeys(rateup_servants))
                # Append to the start
                banners.insert(0, rateup_servants)

    # print(banners)
    # Dedupe banners
    banners = list(dict.fromkeys(banners))
    # print(banners)
    banner_dict[title] = [page.oldest_revision.timestamp, banners]
    # print(banners)

def parse_test():
    for page_name in TEST_PAGES:
        page = pywikibot.Page(SITE, page_name)
        parse(page)

def parse_category(category_name):
    category = pywikibot.Category(SITE, category_name)
    category_length = len(list(category.articles()))
    max_length = category_length + len(INCLUDE_PAGES)
    for i, page in enumerate(category.articles()):
        parse(page, f'{i+1}/{max_length}')
    
    for i, page_name in enumerate(INCLUDE_PAGES):
        page = pywikibot.Page(SITE, page_name)
        parse(page, f'{category_length+i+1}/{max_length}')


def parse_page(page_name):
    page = pywikibot.Page(SITE, page_name)
    
    parse(page)

# Needs fixing
# Goes up the chain of template references to find the original template/banner.
# Test on 3M Downloads Campaign and 13 Bespeckled
def rec_get_ref(original_banner, banner, visited):
    page = pywikibot.Page(SITE, banner)
    num_refs = len(list(page.getReferences(only_template_inclusion=True)))
    # print(f'Found {num_refs} references for {banner}')
    # print(visited)
    # If there are no references, return.
    if num_refs == 0 and banner == original_banner:
        # print(f'In first if condition for {banner}')
        # print(f'No references found for {banner}.')
        # If you can split the banner name by /, then it's a subpage.
        if '/' in banner and banner.split('/')[0] in banner_dict:
            for rateup in banner_dict[banner][1]:
                if rateup not in banner_dict[banner.split('/')[0]][1]:
                    banner_dict[banner.split('/')[0]][1].append(rateup)
            return True
        else:
            return False
    elif num_refs == 0 or banner in visited:
        # print(f'In second if condition for {banner}')
        # print(f'Merging {banner} into {original_banner}...')
        for rateup in banner_dict[original_banner][1]:
            if rateup not in banner_dict[banner][1]:
                banner_dict[banner][1].append(rateup)
        return True
    else:
        # print(f'In else condition for {banner}')
        retval = False
        for reference in page.getReferences(only_template_inclusion=True):
            # print(f'Going to {reference.title()}...')
            if reference.title() in banner_dict:
                # print(f'Entering {reference.title()}...')
                retval = rec_get_ref(original_banner, reference.title(), visited + (banner,))
        return retval

def cleanup():
    print("Checking references")
    max_length = len(list(banner_dict))
    # Loop through the banner_dict.
    for i, banner in enumerate(list(banner_dict)):
        print(f'Cleaning {i+1}/{max_length}: {banner}...')
        ref_exists = rec_get_ref(banner, banner, ())
        # print(ref_exists)
        if ref_exists:
            del banner_dict[banner]

def cleanup_test():
    page = pywikibot.Page(SITE, "FGO 2016 Summer Event/Event Details")
    print(f'Size of {page.title()}: {len(list(page.getReferences(with_template_inclusion=True, follow_redirects=True)))}')
    for reference in page.getReferences():
        print(reference.title())
        page1 = pywikibot.Page(SITE, reference.title())
        for reference1 in page1.getReferences():
            print(f'  {reference1.title()}')
            page2 = pywikibot.Page(SITE, reference1.title())
            for reference2 in page2.getReferences():
                print(f'    {reference2.title()}')
                page3 = pywikibot.Page(SITE, reference2.title())
                for reference3 in page3.getReferences():
                    print(f'      {reference3.title()}')

if TESTING == 1:
    parse_test()
else:
    parse_category(CATEGORY)
cleanup()
# cleanup_test()

# Sort banner_dict by date.
banner_list = []
for banner in banner_dict:
    banner_list.append({
        'name': banner,
        'date': banner_dict[banner][0],
        'rateups': banner_dict[banner][1]
    })
banner_list.sort(key=lambda x: x['date'])

# Save to JSON file
FILE_OLD = "summon_data_test_old.json" if TESTING == 1 else "summon_data_old.json"
FILE_NEW = "summon_data_test.json" if TESTING == 1 else "summon_data.json"
# Copy the preexisting summon_data_test.json file to summon_data_test_old.json
shutil.copy(os.path.join(os.path.dirname(__file__), FILE_NEW), os.path.join(os.path.dirname(__file__), FILE_OLD))
json_obj = jsons.dump(banner_list)
with open(os.path.join(os.path.dirname(__file__), FILE_NEW), 'w') as f:
    f.write(json.dumps(json_obj, indent=2))
# Print the changes from the old file to the new file.
with open(os.path.join(os.path.dirname(__file__), FILE_NEW), 'r') as f1:
    with open(os.path.join(os.path.dirname(__file__), FILE_OLD), 'r') as f2:
        diff = difflib.unified_diff(f2.readlines(), f1.readlines())
        with open(os.path.join(os.path.dirname(__file__), 'diff.txt'), 'w') as f3:
            f3.writelines(diff)

# # parse_page("18M_Downloads_Summoning_Campaign")

