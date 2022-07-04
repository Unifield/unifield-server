#!/usr/bin/env python

import sys
import mypolib as polib

###############################################################################

keep_keywords = []
new_term = True
###############################################################################

def main():

    if len(sys.argv) != 2 or not sys.argv[1]:
        print("Usage: clean.py file.po")
        sys.exit(-1)

    # Load the PO file
    clean(sys.argv[1])

def clean(pofile, output=False):
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
    if output:
        o = open(output, 'w')
    else:
        o = sys.stdout
    for entry in keep:
        o.write("%s\n" % entry)

    if output:
        o.close()

# Sort a list of PO entries according to msgid
def sort_po(po):
    return sorted(list(po), key=lambda m:m.msgid)

# Run main by default
if __name__ == "__main__":
    main()
