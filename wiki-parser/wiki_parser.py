import argparse
from wiki_servants import *
from wiki_banners import *
from wiki_images import *

# Create the parser
parser = argparse.ArgumentParser(description="Parse FGO wiki.")

# Add the optional argument
parser.add_argument('--servants', action='store_true',
                    help='parse servant list before parsing banners')
parser.add_argument('--banners', action='store_true',
                    help='parse banners')
parser.add_argument('--images', action='store_true',
                    help='download images')

# Parse the arguments
args = parser.parse_args()

# If the --update_servants argument was given, parse the servants
if args.servants:
    parse_servants()
    write_to_json()

if args.banners:
    banner_init()
    event_set_na = parse_and_create(EVENT_LIST_NA, "NA")
    event_set_jp = parse_and_create(EVENT_LIST_JP, "JP")

    # Create the JSON representation for event data
    print("Creating event JSON data...")
    create_event_json(event_set_jp, event_set_na)
    print("Creating banner JSON data...")
    create_banner_json(event_set_jp, event_set_na)
    print("Creating servant JSON data...")
    create_servant_json(event_set_jp, event_set_na)

if args.images:
    print("Downloading images...")
    image_init()
    download_images()
