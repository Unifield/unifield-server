#!/usr/bin/env python

import sys
import mypolib as polib

###############################################################################

keep_keywords = []
new_term = True
###############################################################################

def main():

    if len(sys.argv) != 3:
        print "Usage: clean.py liste,of,terms file.po"
        sys.exit(-1)

    keep_keywords = sys.argv[1].split(',')
    # Load the PO file
    pofile = sys.argv[2]
    po = polib.pofile(pofile, wrapwidth=0)

    # Filter entries in the PO
    keep = []
    for entry in po:
        if new_term and not entry.msgstr:
            keep.append(entry)
            continue
        all_occurences = ' '.join([ o[0] for o in entry.occurrences ])
        # Keep this entry if one of the keyword is present in the occurences
        for keyword in keep_keywords:
            if keyword in all_occurences:
                keep.append(entry)

    # Sort kept entries according to msgid
    keep = sort_po(keep)

    # Display kept entries
    for entry in keep:
        print entry

# Sort a list of PO entries according to msgid
def sort_po(po):
    return sorted(list(po), key=lambda m:m.msgid)

# Run main by default
if __name__ == "__main__":
    main()
