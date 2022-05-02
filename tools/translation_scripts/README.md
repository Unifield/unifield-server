
How to use these scripts
------------------------

- 1. Export some translations from Unifield
- 2. Edit and run 'clean.py' to extract the relevant strings you want to
     translate and sort them alphabetically
- 3. Do the translation
- 4. Use 'merge.py' to merge your work into the 'master' file
- 5. Look at the diff between the merged file and the original master file to
     make sure everything looks okay
- 6. Replace the master file with the new merge file, and reimport the
     translation in unifield to check everything is okay!

About generate_translation_file
-------------------------------

- The options:
  - runbot ('-rb'): Non-mandatory, will target a runbot to take the translation
    file from there and save the file locally.
  - database ('-db'): Mandatory, except when '-rb' is used. It will try to use the
    HQ1 database from the runbot if none is given. The expected database 
    will be used in all other cases.
  - password ('-p'): Non-mandatory, will be 'admin' by default.
  - modules ('-m'): Non-mandatory, list of modules to get the translation from.
    Each module should be separated by a comma (ie: stock,msf_profile,etc...). If
    a module isn't recognized, it will be ignored. If no module is given or all 
    modules have been ignored, all untranslated strings
    will be in the new file.
  - lang ('-l'): Non-mandatory and french (code: 'fr_MF') by default. The lang 
    must be active and translatable to be usable.
- If the script does not find a translation file within 300 seconds, it will stop 
  without going further.
- After the script is done, the new file will be located in the addons/msf_profile directory 
  linked to the project where the script is. The original translation file will still be
  there, with the name 'fr_MF_old.po'. Be careful not to commit it.

Exemple of use: python generate_translation_file.py -db HQ1C1P1 -p admin -m stock,msf_profile

Possible improvements
---------------------

clean.py and merge.py could be improved with proper arguments parsing.

E.g. have for clean.py : 

--keep-occurences keyword1 keyword2
(Keep only entries with occurences containing these keywords)

--find-existing-translation
(Look at the master file for existing translation and pre-fill the output with
those)

...

