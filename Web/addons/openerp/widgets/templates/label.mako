<label for="${name}" ${ "class=help" if help else "" } 
% if bold:
 style="font-weight: bold;"
% endif
>${string or ''}</label>
% if help:
    <span class="help">?</span>
% endif
:
