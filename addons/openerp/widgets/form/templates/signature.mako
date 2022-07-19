<p id="sig_${name}" />
<input id="${name}" name="${name}" type="hidden"/>
% if editable:
<br />
<button id="${name}_clear" type="button">Clear</button>
% endif



<script>
$('#sig_${name}').signature({syncField: '#${name}'});
% if value:
    $('#sig_${name}').signature('draw', '${value|n}');
% endif
% if not editable:
   $('#sig_${name}').signature('disable');
% endif
</script>


% if editable:
<script>
$('#${name}_clear').click(function() {
    $('#sig_${name}').signature('clear');
});
</script>
% endif
