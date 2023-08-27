import pywikibot
import mwparserfromhell
import jsons
import os
import re2

CATEGORY = 'Servant_ID_Order'

FILTERS = {
    # \n -> ', '
    r'<br/>\\n': r', ', 
    # \n<!-- DO NOT Remove. This is Used for Dynamic Servant Filter. --->, <!--Do not remove-->, <br/>, <sup>...?...</sup> -> ''
    r'\\n<!--.*?-->|<!--.*?-->|<sup>.*?\?.*?</sup>': r'', 
    # \n -> ', '
    r'\\n|<br/>': r', ', 
    # [[w:c:typemoon:Shirou Emiya|Emiya Shirou]] -> Shirou Emiya
    r'\'\'\'(.*?)\'\'\'': r'\1', 
    # [[w:c:typemoon:Shirou Emiya|Emiya Shirou]] -> Shirou Emiya
    r'\[\[:*w:c:[Tt]ypemoon:.*?\|(.*?)\]\]': r'\1', 
    # [[Iskandar|Young Iskandar]] -> Young Iskandar
    r'\[\[[^\]]*?\|(.*?)\]\]': r'\1', 
    # [[Sigurd]] -> Sigurd
    r'\[\[(.*?)\]\]': r'\1', 
    # {{Ruby|King of Gods|Pharaoh}} -> King of Gods
    r'{{[Rr]uby\|(.*?)\|.*?}}': r'\1', 
    # {{nihongo|King of Knights|騎士王|Kishi-ō}} -> King of Knights
    r'{{[Nn]ihongo\|(.*?)(\|.*?}}|}})': r'\1', 
    # {{Tooltip|Saint Graph name|玉藻の前}} -> 玉藻の前
    r'{{[Tt]ooltip\|.*?\|(.*?)}}': r'\1', 
    # <span class=\"spoiler-msg\">Fairy Knight Galahad</span> -> [Fairy Knight Galahad]
    r'<span class=\\\"spoiler-msg\\\">(.*?)</span>': r'[\1]'
}

def json_filter(json_str):
    # {{Custom Kanji|jin}} -> 神
    json_str = json_str.replace(r'{{Custom Kanji|jin}}', r'\u795e')
    # 𝘛𝘰𝘣𝘪 𝘒𝘢𝘵ō -> Tobi Katō (replace surrogate pair character)
    json_str = json_str.replace(
        r'\ud835\ude1b\ud835\ude30\ud835\ude23\ud835\ude2a \ud835\ude12\ud835\ude22\ud835\ude35\u014d',
        r'Tobi Kato'
    )
    # Apply regex find and replaces
    for filter in FILTERS:
        json_str = re2.compile(filter).sub(FILTERS[filter], json_str)
    # \" -> \\" (running .encode and .decode unescapes ")
    json_str = json_str.replace(r'\"', r'\\"')
    return json_str

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
    category = pywikibot.Category(site, category_name)

    # Iterate through each servant's page.
    for page in category.articles():
        # Get name of servant
        title = page.title()
        # Parse servant info
        text = page.text
        wikicode = mwparserfromhell.parse(text)

        # Find the template containing the servant details
        filtered = wikicode.filter_templates()
        for template in filtered:
            if template.name.strip() == 'CharactersNew':
                # Find the ID of the servant
                id_val = 0
                try:
                    id_val = template.get("id").value.strip()
                except ValueError:
                    print(f' - No ID found for {title}')
                    break
                # If the ID is valid, export the servant's data
                if id_val.isdigit():
                    print(f'{template.get("id").value.strip()}: {title}')
                    servant_dict[int(id_val)] = Servant(title, template)
                else:
                    print(f' - No ID found for {title}')
                break

parse(CATEGORY)

# Save to JSON file
with open(os.path.join(os.path.dirname(__file__), 'servant_data.json'), 'w') as f:
    # Convert unicode \uXXXX to actual characters
    f.write(json_filter(jsons.dumps(servant_dict)).encode().decode('unicode-escape'))
