import argparse
from wiki_servants import *
from wiki_banners import *

# Create the parser
parser = argparse.ArgumentParser(description="Parse FGO wiki.")

# Add the optional argument
parser.add_argument('--update_servants', action='store_true',
                    help='parse servant list before parsing banners')

# Parse the arguments
args = parser.parse_args()

# If the --update_servants argument was given, parse the servants
if args.update_servants:
    parse_servants()
    write_to_json()

initialize()
parse_and_create(EVENT_LIST_NA, EVENT_SET_NA, "NA")
parse_and_create(EVENT_LIST_JP, EVENT_SET_JP, "JP")