import pywikibot
import mwparserfromhell
import jsons
import json
import os
import re
import requests
from tqdm import tqdm

BAR_FORMAT_SERVANTS = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

CATEGORY = 'Servant ID Order'

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
    # {{Tooltip|Saint Graph name|玉藻の前}} -> 玉藻の前
    # {{Tooltip|フローレンス・ナイチンゲール}} -> フローレンス・ナイチンゲール
    # {{Tooltip|NA Localization|2=Romulus=Quirinus}} -> Romulus=Quirinus
    r'{{[Tt]ooltip(?:\|.*?)?\|(?:2=)?(.*?)}}': r'\1', 
    # {{nihongo|King of Knights|騎士王|Kishi-ō}} -> King of Knights
    r'{{[Nn]ihongo\|(.*?)(\|.*?}}|}})': r'\1', 
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
        json_str = re.compile(filter).sub(FILTERS[filter], json_str)
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
        self.class_type = template.get("class").value.strip()
        self.rarity = int(template.get("stars").value.strip())
        self.attribute = template.get("attribute").value.strip()
        self.gender = template.get("gender").value.strip()
        self.alignment = template.get("alignment").value.strip()
        self.traits = template.get("traits").value.strip()
        self.image_file = ""

SERVANT_LIST = []
ATLAS_ACADEMY_DATA = None

def fetch_atlas_academy_data():
    """
    Fetch and cache the servant data from Atlas Academy API.
    """
    global ATLAS_ACADEMY_DATA
    if ATLAS_ACADEMY_DATA is None:
        try:
            print('Fetching servant data from Atlas Academy API...')
            response = requests.get('https://api.atlasacademy.io/export/JP/nice_servant.json', timeout=30)
            response.raise_for_status()
            # Map by collectionNo instead of id
            ATLAS_ACADEMY_DATA = {servant.get('collectionNo'): servant for servant in response.json() if servant.get('collectionNo') is not None}
            print(f'Successfully loaded data for {len(ATLAS_ACADEMY_DATA)} servants')
        except Exception as e:
            print(f"Error fetching Atlas Academy data: {e}")
            ATLAS_ACADEMY_DATA = {}
    return ATLAS_ACADEMY_DATA

def get_servant_thumbnail(servant_id, servants_data):
    """
    Get the servant thumbnail image filename from Atlas Academy data.
    Returns the first ascension face image filename, or empty string if not found.
    
    Args:
        servant_id: The servant's collection number
        servants_data: Pre-fetched Atlas Academy servant data dictionary
    """
    # Match servant_id with collectionNo field
    if servant_id in servants_data:
        servant = servants_data[servant_id]
        # Get the face images for ascensions
        extra_assets = servant.get('extraAssets', {})
        faces = extra_assets.get('faces', {})
        ascension_faces = faces.get('ascension', {})
        
        # Return the first ascension face image filename
        if '1' in ascension_faces:
            url = ascension_faces['1']
            # Extract just the filename from the URL
            return url.split('/')[-1] if url else ''
        
        # If no ascension 1, try to get any available face
        if ascension_faces:
            # Get the first available ascension
            first_key = sorted(ascension_faces.keys())[0]
            url = ascension_faces[first_key]
            # Extract just the filename from the URL
            return url.split('/')[-1] if url else ''
    
    return ""

def parse_servants():
    print('Parsing servants...')
    # Fetch Atlas Academy data once at the beginning
    servants_data = fetch_atlas_academy_data()
    
    # Load the servants page
    site = pywikibot.Site()
    category = pywikibot.Category(site, CATEGORY)
    category_length = len(list(category.articles()))

    # Iterate through each servant's page.
    for page in (pbar := tqdm(category.articles(), total=category_length, bar_format=BAR_FORMAT_SERVANTS)):
        # Get name of servant
        title = page.title()
        pbar.set_postfix_str(title)
        # Skip if (Arcade) is in title
        if "(Arcade)" in title:
            continue
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
                    pbar.clear()
                    print(f'No ID found for {title}')
                    break
                # If the ID is valid, export the servant's data
                if id_val.isdigit():
                    servant = Servant(title, template)
                    # Get thumbnail image from pre-fetched Atlas Academy data
                    servant.image_file = get_servant_thumbnail(servant.id, servants_data)
                    SERVANT_LIST.append(servant)
                else:
                    pbar.clear()
                    print(f'No ID found for {title}')
                break

def write_to_json():
    print('Writing servant data to JSON...')
    # Save to JSON file
    with open(os.path.join(os.path.dirname(__file__), 'servant_details.json'), 'w') as f:
        json_obj = jsons.dump(SERVANT_LIST)
        # Convert unicode \uXXXX to actual characters
        f.write(json_filter(json.dumps(json_obj, indent=2)).encode().decode('unicode-escape'))
