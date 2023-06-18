import pywikibot
import json
from django.utils.text import slugify

def grab_title(link):
    site = pywikibot.Site()
    page = pywikibot.Page(site, link)
    return page.title()

# Open the JSON file and load the data
with open('../banner_data.json') as f:
    data = json.load(f)

correction_list = []

# Loop through the list.
for banner in data:
    link = banner['wiki_link']
    # If link does not contain fategrandorder.wikia.com, print it out.
    if not link or 'fategrandorder.' not in link:
        print(banner['name'])
        correction = {}
        correction['name'] = banner['name']
        correction['old_link'] = banner['wiki_link']
        correction['start_date'] = banner['start_date']
        correction['end_date'] = banner['end_date']
        correction['banner_id'] = banner['banner_id']
        correction['region'] = banner['region']
        correction['new_link'] = ''
        correction_list.append(correction)

# Export to JSON
with open("correction_list.json", 'w') as f:
    json.dump(correction_list, f, indent=4)
