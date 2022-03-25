
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

- The script is usable by default in local environment, and consider you are 
  using it while being in the tools/translation_scripts directory.
- It will only generate a file for the french translation.
- The options '-db' for database and  for '-p' for password are mandatory.
- The option '-m' for modules is optional and can be a list of several modules,
  each separated by a comma. Any module not found will be ignored and if none
  are found, all untranslated string will be in the new file.
- If the script does not find a translation file within 300 seconds, it will stop 
  without going further.
- After the script is done, the original translation file will still be there, with the 
  name 'fr_MF_old.po'. Be careful not to commit it.

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

