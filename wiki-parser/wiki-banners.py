import pywikibot
import mwparserfromhell
import jsons
import os
import re2

CATEGORY = 'Interlude_Campaign_10_Summoning_Campaign'

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

    # Find the template containing the servant details
    filtered = wikicode.filter_tags()
    print(filtered[1])
    # for template in filtered:
    #     print(template)
            # if template.name.strip() == 'CharactersNew':
            #     # Find the ID of the servant
            #     id_val = 0
            #     try:
            #         id_val = template.get("id").value.strip()
            #     except ValueError:
            #         print(f' - No ID found for {title}')
            #         break
            #     # If the ID is valid, export the servant's data
            #     if id_val.isdigit():
            #         print(f'{template.get("id").value.strip()}: {title}')
            #         servant_dict[int(id_val)] = Servant(title, template)
            #     else:
            #         print(f' - No ID found for {title}')
            #     break

parse(CATEGORY)

# # Save to JSON file
# with open(os.path.join(os.path.dirname(__file__), 'servant_data.json'), 'w') as f:
#     # Convert unicode \uXXXX to actual characters
#     f.write(json_filter(jsons.dumps(servant_dict)).encode().decode('unicode-escape'))
