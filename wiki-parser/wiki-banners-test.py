import pywikibot
import mwparserfromhell
import wikitextparser as wtp
import jsons
import os
import re2

CATEGORY = '"The_Old_Man_of_the_Mountain"_Summoning_Campaign'

MATCHES = [
    "New Servant",
    "Rate-Up Servants",
]

servant_data = None
# Import servant_data.json as json.
with open(os.path.join(os.path.dirname(__file__), 'servant_data.json')) as f:
    servant_data = jsons.loads(f.read())

# The json is a dictionary, where every value is also a dictionary. Make a set out of the name field in the dictionary in the value.
servant_names = set([servant_data[servant]['name'] for servant in servant_data])

class Servant:
    def __init__(self, title, template):
        self.id = int(template.get("id").value.strip())
        self.name = title
        self.jp_name = template.get("jname").value.strip()
        try:
            self.aliases = template.get("aka").value.strip()
        except ValueError:
            self.aliases = ""
        self.voice_actor = template.get("voicea").value.strip()
        self.illustrator = template.get("illus").value.strip()
        self.release = template.get("release").value.strip()
        self.class_type = template.get("class").value.strip()
        self.rarity = int(template.get("stars").value.strip())
        self.attribute = template.get("attribute").value.strip()
        self.gender = template.get("gender").value.strip()
        self.alignment = template.get("alignment").value.strip()
        self.traits = template.get("traits").value.strip()

servant_dict = {}

def parse(category_name):
    # Load the servants page
    site = pywikibot.Site()
    page = pywikibot.Page(site, category_name)

    # Iterate through each servant's page.
    # for i, page in enumerate(category.articles()):
    #     if i > 1:
    #         break
    # Get name of servant
    title = page.title()
    # Parse servant info
    text = page.text

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
        class_type = None
        try:
            class_type = tag.get("class").value.strip()
        except ValueError:
            pass
        if class_type != 'wikitable' or not any([x in tag for x in MATCHES]):
            continue
        table = mwparserfromhell.parse(tag)
        templates = table.filter_templates()
        rateup_servants = []
        for template in templates:
            if str(template.name) in servant_names:
                rateup_servants.append(str(template.name))

        rateup_servants = list(dict.fromkeys(rateup_servants))

        banners.append(rateup_servants)

    # If a page that uses wikilinks only
    if not banners:
        links = wikicode.filter_wikilinks()
        rateup_servants = []
        for link in links:
            if str(link.title) in servant_names:
                rateup_servants.append(str(link.title))
        rateup_servants = list(dict.fromkeys(rateup_servants))
        banners.append(rateup_servants)

    print(banners)

parse(CATEGORY)

