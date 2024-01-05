import os
import pywikibot
import jsons
from tqdm import tqdm

# Define format of progress bar.
BAR_FORMAT_IMAGES = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

DIR_PATH = None
SITE = None
EVENT_DATA = None
IMAGES = None

def image_init():
    global DIR_PATH
    global SITE
    global EVENT_DATA
    global IMAGES

    DIR_PATH = os.path.dirname(__file__) # Path to the directory of this file
    SITE = pywikibot.Site() # Wiki site

    # Import the servant data.
    with open(os.path.join(DIR_PATH, 'event_data.json')) as f:
        EVENT_DATA = jsons.loads(f.read())

    # Get the names and IDs of all the servants.
    IMAGES = [event['image_file'] for event in EVENT_DATA]

def download_images():
    # If folder "imgs" exists...
    if os.path.exists("imgs"):
        # Get a list of all the files in the folder.
        files = set(os.listdir("imgs"))
        # Make a list of all the images that are in IMAGES but not in files.
        images_to_download = [image for image in IMAGES if image not in files]
    else:
        os.makedirs("imgs")
        images_to_download = IMAGES

    for image_file in (pbar := tqdm(images_to_download, bar_format=BAR_FORMAT_IMAGES)):
        pbar.set_postfix_str(image_file)
        page = pywikibot.FilePage(SITE, image_file)
        page.download(filename=f'imgs/{image_file}.!')
