import argparse
from wiki_servants import *
from wiki_banners import *

# Create the parser
parser = argparse.ArgumentParser(description="Parse FGO wiki.")

# Add the optional argument
parser.add_argument('--servants', action='store_true',
                    help='parse servant list before parsing banners')
parser.add_argument('--banners', action='store_true',
                    help='parse banners')

# Parse the arguments
args = parser.parse_args()

# If the --update_servants argument was given, parse the servants
if args.servants:
    parse_servants()
    write_to_json()

if args.banners:
    initialize()
    parse_and_create(EVENT_LIST_NA, EVENT_SET_NA, "NA")
    parse_and_create(EVENT_LIST_JP, EVENT_SET_JP, "JP")

    # Create the JSON representation for event data
    print("Creating event JSON data...")
    create_event_json(EVENT_SET_JP, EVENT_SET_NA)
    print("Creating banner JSON data...")
    create_banner_json(EVENT_SET_JP, EVENT_SET_NA)
    print("Creating servant JSON data...")
    create_servant_json(EVENT_SET_JP, EVENT_SET_NA)