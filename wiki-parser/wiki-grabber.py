import pywikibot
import os
from django.utils.text import slugify

CATEGORY = 'Summoning_Campaign'
OUT_DIR = 'banner-pages'

def parse(category_name):
    FILE_NAMES = []
    site = pywikibot.Site()
    category = pywikibot.Category(site, category_name)
    count = 0
    for page in category.articles():
        count += 1
        title = page.title()
        print(f'Saving page {count}: {title}...')

        text = page.text
        
        filename = OUT_DIR + '/' + slugify(title)
        if filename in FILE_NAMES:
            i = 1
            while filename in FILE_NAMES:
                filename = filename + '_' + str(i)
                i += 1
        FILE_NAMES.append(filename)

        with open(filename + '.txt', 'w', encoding='utf-8') as f:
            f.write(str(text))
    return count

# If directory doesn't exist, create one called "banner-pages"
if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)

num = parse(CATEGORY)

print(f'Saved {num} pages from {CATEGORY}.')
print('Done.')