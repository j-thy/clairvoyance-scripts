import pywikibot
import mwparserfromhell
import wikitextparser as wtp
import jsons
import os
import re2
import sys

CATEGORY = 'Summoning_Campaign'

TABLE_MATCHES = [
    "New Servant",
    "Rate-Up Servants",
    "Rate-Up Limited Servants",
    "Rate-Up Servant"
]

LINK_MATCHES = [
    "Draw rates",
    "Summoning Rate",
    "increased draw rates"
]

TEST_PAGES = [
    "Fate/Grand Order ～8th Anniversary～ Destiny Order Summoning Campaign",
    "Fate/Grand Order ～8th Anniversary～",
    "Fate/Grand Order ～8th Anniversary～ Summoning Campaign",
    "Fate/Grand Order ～8th Anniversary～ Summoning Campaign I",
    "Fate/Grand Order ～8th Anniversary～ Summoning Campaign II",
]

SITE = pywikibot.Site()

servant_data = None
# Import servant_data.json as json.
with open(os.path.join(os.path.dirname(__file__), 'servant_data.json')) as f:
    servant_data = jsons.loads(f.read())

# The json is a dictionary, where every value is also a dictionary. Make a set out of the name field in the dictionary in the value.
servant_names = set([servant_data[servant]['name'] for servant in servant_data])
banner_dict = {}

def parse(page, progress=None):
    # Iterate through each servant's page.
    # for i, page in enumerate(category.articles()):
    #     if i > 1:
    #         break
    # Get name of servant
    title = page.title()
    # Parse servant info
    text = page.text

    if progress:
        print(f'Parsing {progress}: {title}...')
    else:
        print(f'Parsing {title}...')
    # print(text)

    wikicode = mwparserfromhell.parse(text)
    # print(text)

    banners = []

    # Find the template containing the servant details
    tags = wikicode.filter_tags()

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
        table = mwparserfromhell.parse(tag)
        templates = table.filter_templates()
        rateup_servants = []
        for template in templates:
            if str(template.name) in servant_names:
                rateup_servants.append(str(template.name))

        if rateup_servants:
            rateup_servants.sort()
            rateup_servants = tuple(dict.fromkeys(rateup_servants))
            banners.append(rateup_servants)

    # print(banners)
    # print(text)
    # If a page that uses wikilinks only
    if not banners and any([x in text for x in LINK_MATCHES]):
        # print("test")
        links = wikicode.filter_wikilinks()
        # print(links)
        rateup_servants = []
        for link in links:
            # print(link.title)
            if str(link.title) in servant_names:
                rateup_servants.append(str(link.title))

        if rateup_servants:
            rateup_servants.sort()
            rateup_servants = tuple(dict.fromkeys(rateup_servants))
            banners.append(rateup_servants)

    # print(banners)
    # Dedupe banners
    banners = list(dict.fromkeys(banners))
    banner_dict[title] = [page.oldest_revision.timestamp, banners]
    # print(banners)

def parse_test():
    for page_name in TEST_PAGES:
        page = pywikibot.Page(SITE, page_name)
        parse(page)

def parse_category(category_name):
    category = pywikibot.Category(SITE, category_name)
    max_length = len(list(category.articles()))
    for i, page in enumerate(category.articles()):
        parse(page, f'{i+1}/{max_length}')

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
        return False
    elif num_refs == 0 or banner in visited:
        # print(f'In second if condition for {banner}')
        # print(f'Merging {banner} into {original_banner}...')
        banner_dict[banner][1].extend(banner_dict[original_banner][1])
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
    page = pywikibot.Page(SITE, "Fate/Grand Order ～8th Anniversary～ Destiny Order Summoning Campaign")
    for reference in page.getReferences(only_template_inclusion=True):
        print(reference.title())
        page1 = pywikibot.Page(SITE, reference.title())
        for reference1 in page1.getReferences(only_template_inclusion=True):
            print(f'  {reference1.title()}')
            page2 = pywikibot.Page(SITE, reference1.title())
            for reference2 in page2.getReferences(only_template_inclusion=True):
                print(f'    {reference2.title()}')
                page3 = pywikibot.Page(SITE, reference2.title())
                for reference3 in page3.getReferences(only_template_inclusion=True):
                    print(f'      {reference3.title()}')

# parse_category(CATEGORY)
parse_test()
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
with open(os.path.join(os.path.dirname(__file__), 'summon_data.json'), 'w') as f:
    f.write(jsons.dumps(banner_list))

# # parse_page("18M_Downloads_Summoning_Campaign")

