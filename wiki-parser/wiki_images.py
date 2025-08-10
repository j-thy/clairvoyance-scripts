import os
import pywikibot
import jsons
import requests
from tqdm import tqdm

# Define format of progress bar.
BAR_FORMAT_IMAGES = "{l_bar}{bar:50}{r_bar}{bar:-50b}"

DIR_PATH = None
SITE = None
EVENT_DATA = None
SERVANT_DATA = None
IMAGES = None
SERVANT_IMAGES = None

def image_init():
    global DIR_PATH
    global SITE
    global EVENT_DATA
    global SERVANT_DATA
    global IMAGES
    global SERVANT_IMAGES

    DIR_PATH = os.path.dirname(__file__) # Path to the directory of this file
    SITE = pywikibot.Site() # Wiki site

    # Import the event data.
    with open(os.path.join(DIR_PATH, 'event_data.json')) as f:
        EVENT_DATA = jsons.loads(f.read())

    # Import the servant data.
    with open(os.path.join(DIR_PATH, 'servant_data.json')) as f:
        SERVANT_DATA = jsons.loads(f.read())

    # Get the image files of all the events.
    IMAGES = [event['image_file'] for event in EVENT_DATA]
    
    # Get the image files of all the servants.
    SERVANT_IMAGES = [servant['image_file'] for servant in SERVANT_DATA]

def download_event_images():
    # Create imgs root folder if it doesn't exist
    if not os.path.exists("imgs"):
        os.makedirs("imgs")
    
    # If folder "imgs/imgs_events" exists...
    if os.path.exists("imgs/imgs_events"):
        # Get a list of all the files in the folder.
        files = set(os.listdir("imgs/imgs_events"))
        # Make a list of all the images that are in IMAGES but not in files.
        images_to_download = [image for image in IMAGES if image not in files]
    else:
        os.makedirs("imgs/imgs_events")
        images_to_download = IMAGES

    for image_file in (pbar := tqdm(images_to_download, bar_format=BAR_FORMAT_IMAGES, desc="Downloading event images")):
        pbar.set_postfix_str(image_file)
        page = pywikibot.FilePage(SITE, image_file)
        page.download(filename=f'imgs/imgs_events/{image_file}.!')

def download_servant_images():
    # Create imgs root folder if it doesn't exist
    if not os.path.exists("imgs"):
        os.makedirs("imgs")
    
    # If folder "imgs/imgs_servants" exists...
    if os.path.exists("imgs/imgs_servants"):
        # Get a list of all the files in the folder.
        files = set(os.listdir("imgs/imgs_servants"))
        # Make a list of all the images that are in SERVANT_IMAGES but not in files.
        images_to_download = [image for image in SERVANT_IMAGES if image not in files]
    else:
        os.makedirs("imgs/imgs_servants")
        images_to_download = SERVANT_IMAGES

    for image_file in (pbar := tqdm(images_to_download, bar_format=BAR_FORMAT_IMAGES, desc="Downloading servant images")):
        pbar.set_postfix_str(image_file)
        url = f"https://static.atlasacademy.io/JP/Faces/{image_file}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            with open(f'imgs/imgs_servants/{image_file}', 'wb') as f:
                f.write(response.content)
        except requests.RequestException as e:
            print(f"Failed to download {image_file}: {e}")
