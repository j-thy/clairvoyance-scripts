import pywikibot
import mwparserfromhell

CATEGORY = 'Servant_ID_Order'

def parse(category_name):
    FILE_NAMES = []
    site = pywikibot.Site()
    category = pywikibot.Category(site, category_name)
    done = 0
    for page in category.articles():
        done = 0
        title = page.title()
        # print(title)
        text = page.text
        # print(text)
        wikicode = mwparserfromhell.parse(text)
        filtered = wikicode.filter_templates()
        # print(f'{filtered[1].get("id").value.strip()}: {title}')
        for template in filtered:
            if template.name.strip() == 'CharactersNew':
                done = 1
                try:
                    id_val = template.get("id").value.strip()
                    if id_val.isdigit():
                        print(f'{template.get("id").value.strip()}: {title}')
                    else:
                        print(f' - No ID found for {title}')
                except ValueError:
                    print(f' - No ID found for {title}')
                break
        if done == 0:
            print(f' - No template found for {title}')

parse(CATEGORY)
