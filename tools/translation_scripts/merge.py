#!/usr/bin/env python

import mypolib as polib
import argparse

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-y', action='store_true', help='In case of duplication use your translation')
    group.add_argument('-m', action='store_true', help='In case of duplication use the master one')
    parser.add_argument('file_to_merge', help='PO to be merger')
    parser.add_argument('master', help='master PO file (fr_MF.po)')

    option = parser.parse_args()

    # Load the PO files
    Merge(option.file_to_merge, option.master, option.y, option.m).merge()

class Merge():
    def __init__(self, my_po, master_po,  use_my=False, use_master=False):
        self.my_po = self.sort_po(polib.pofile(my_po, wrapwidth=0))
        self.master_po = polib.pofile(master_po, wrapwidth=0)
        self.output_po = master_po + '.merged'
        self.use_my = use_my
        self.use_master = use_master

    def merge(self):
        #display_untranslated_strings()
        self.display_existing_translations()
        self.do_merge()
        self.save()


    def sort_po(self, po):
        return sorted(list(po), key=lambda m:m.msgid)


    def save(self):
        self.master_po.save(self.output_po)
        print("Merge output : %s" % self.output_po)


    def get_modules(self, entry):
        return [x.strip() for x in entry.comment.replace('modules:','').replace('module:','').split(',')]

    def display_existing_translations(self):
        master_ids = [ m.msgid for m in self.master_po ]
        print("The following entries are already translated in master PO file:")
        for entry in self.my_po:

            if entry.msgid in master_ids:
                master_translations = [ m.msgstr for m in self.master_po if m.msgid == entry.msgid]
                if entry.msgstr in master_translations:
                    continue

                print("----")
                print("[  Original string  ] %s" % entry.msgid)
                print("[ Your  translation ] %s" % entry.msgstr)
                print("[Master translations] %s" % " | ".join(master_translations))
                ret = ""
                if self.use_my:
                    ret = 'y'
                elif self.use_master:
                    ret = 'm'

                while ret not in ('y', 'm'):
                    ret = input("keep Yours [y] or use fisrt Master [m] ?")
                    ret = ret.lower()
                if ret == 'm':
                    entry.msgstr = master_translations[0]

    def merge_occurrences(self, new_entry, existing_entry):

        for o in new_entry.occurrences:
            if not o in existing_entry.occurrences:
                existing_entry.occurrences.append(o)
        new_module = set(self.get_modules(new_entry)) - set(self.get_modules(existing_entry))
        if new_module:
            existing_entry.comment.replace('module:', 'modules:')
            existing_entry.comment +=', %s' % ','.join(list(new_module))

    def do_merge(self):
        for entry in self.my_po:

            existing_translation = [ e for e in self.master_po
                                     if  e.msgid == entry.msgid \
                                     and e.msgstr == entry.msgstr ]

            # If there's already an existing translation with same id/str,
            # only add an occurence
            if existing_translation:
                existing_translation = existing_translation[0]
                self.merge_occurrences(entry, existing_translation)
            # Otherwise, add a new entry
            else:
                self.master_po.append(entry)




if __name__ == "__main__":
    main()
