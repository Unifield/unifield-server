#!/usr/bin/env python

import sys
import mypolib as polib

my_po = None
master_po = None
output_po = None

def main():
    global my_po, master_po, output_po

    if len(sys.argv) != 3 or not sys.argv[1] or not sys.argv[2]:
        print "Usage: merge.py file_to_merge.po master.po"
        sys.exit(-1)

    # Load the PO files
    my_po = sys.argv[1]
    master_po = sys.argv[2]
    output_po = master_po + ".merged"

    my_po = sort_po(polib.pofile(my_po, wrapwidth=0))
    master_po = polib.pofile(master_po, wrapwidth=0)

    #display_untranslated_strings()
    display_existing_translations()
    do_merge()
    save()


def sort_po(po):
    return sorted(list(po), key=lambda m:m.msgid)


def save():
    master_po.save(output_po)
    print "Merge output : %s" % output_po


def display_existing_translations():
    master_ids = [ m.msgid for m in master_po ]
    print "The following entries are already translated in master PO file:"
    for entry in my_po:

        if entry.msgid in master_ids:
            master_translations = [ m.msgstr for m in master_po if m.msgid == entry.msgid]
            if entry.msgstr in master_translations:
                continue

            print "----"
            print "[  Original string  ] %s" % entry.msgid
            print "[ Your  translation ] %s" % entry.msgstr
            print "[Master translations] %s" % " | ".join(master_translations)


def merge_occurrences(new_entry, existing_entry):

    for o in new_entry.occurrences:
        if not o in existing_entry.occurrences:
            existing_entry.occurrences.append(o)


def do_merge():
    for entry in my_po:

        existing_translation = [ e for e in master_po
                                 if  e.msgid == entry.msgid \
                                 and e.msgstr == entry.msgstr ]

        # If there's already an existing translation with same id/str,
        # only add an occurence
        if existing_translation:
            existing_translation = existing_translation[0]
            merge_occurrences(entry, existing_translation)
        # Otherwise, add a new entry
        else:
            master_po.append(entry)




main()
