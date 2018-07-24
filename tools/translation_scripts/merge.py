#!/usr/bin/env python

import mypolib as polib
import argparse

my_po = None
master_po = None
output_po = None
option = None
def main():
    global my_po, master_po, output_po, option


    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-y', action='store_true', help='In case of duplication use your translation')
    group.add_argument('-m', action='store_true', help='In case of duplication use the master one')
    parser.add_argument('file_to_merge', help='PO to be merger')
    parser.add_argument('master', help='master PO file (fr_MF.po)')

    option = parser.parse_args()

    # Load the PO files
    my_po = option.file_to_merge
    master_po = option.master
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


def get_modules(entry):
    return [x.strip() for x in entry.comment.replace('modules:','').replace('module:','').split(',')]

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
            ret = ""
            if option.y:
                ret = 'y'
            elif option.m:
                ret = 'm'

            while ret not in ('y', 'm'):
                ret = raw_input("keep Yours [y] or use fisrt Master [m] ?")
                ret = ret.lower()
            if ret == 'm':
                entry.msgstr = master_translations[0]

def merge_occurrences(new_entry, existing_entry):

    for o in new_entry.occurrences:
        if not o in existing_entry.occurrences:
            existing_entry.occurrences.append(o)
    new_module = set(get_modules(new_entry)) - set(get_modules(existing_entry))
    if new_module:
        existing_entry.comment.replace('module:', 'modules:')
        existing_entry.comment +=', %s' % ','.join(list(new_module))

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
