<p id="sig_${name}" />
<input id="${name}" name="${name}" />
<script>
$('#sig_${name}').signature({syncField: '#${name}'});
% if value:
    $('#sig_${name}').signature('draw', '${value|n}');
    //$('#sig_${name}').signature().html('ooooo');
% endif
</script>
