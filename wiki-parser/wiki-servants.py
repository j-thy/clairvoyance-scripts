import pywikibot
import mwparserfromhell

CATEGORY = 'Servant_ID_Order'

def parse(category_name):
    FILE_NAMES = []
    site = pywikibot.Site()
    category = pywikibot.Category(site, category_name)
    count = 0
    for page in category.articles():
        title = page.title()
        print(title)
        text = page.text
        # print(text)
        wikicode = mwparserfromhell.parse(text)
        filtered = wikicode.filter_templates()
        print(filtered[1].get("id").value)
        break

parse(CATEGORY)
