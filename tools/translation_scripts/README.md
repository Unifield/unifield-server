
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

