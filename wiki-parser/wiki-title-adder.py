import pywikibot
import os
import argparse
import json
from django.utils.text import slugify

def grab_title(link):
    site = pywikibot.Site()
    page = pywikibot.Page(site, link)
    return page.title()

# Create an argument parser
parser = argparse.ArgumentParser(description='Augment the banner_data.json with wiki-version titles.')

# Add a positional argument for the JSON file
parser.add_argument('json_file', help='banner data JSON file')

# Parse the command line arguments
args = parser.parse_args()

# Open the JSON file and load the data
with open(args.json_file) as f:
    data = json.load(f)

# Loop through the list.
for banner in data:
    link = banner['wiki_link']
    # Split url to get https://fategrandorder.fandom.com/wiki/Nero_Fest_%26_Battle_in_NY_2022_Summoning_Campaign everything after wiki.
    link = link.split('wiki/')[1]
    title = grab_title(link)
    # Add title to the banner
    banner['wiki_name'] = title

# Export to json.
with open("banner_data_new.json", 'w') as f:
    json.dump(data, f, indent=4)