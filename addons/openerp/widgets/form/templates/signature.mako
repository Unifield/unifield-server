<input id="${name}" name="${name}" type="hidden"/>
<table class="fields">
    <tr>
        <td><p id="sig_${name}" /></td>
    <td>
<div>
    <button id="${name}_clear" type="button">Clear Signature</button>
</div>
    </td>
    </tr>
</table>


<script>
$('#sig_${name}').signature({syncField: '#${name}'});
$('#sig_${name}').signature('option', 'syncFormat', 'PNG');
set_preview();
change_text();
</script>

<script>

$('#${name}_clear').click(function() {
    $('#sig_${name}').signature('clear');
    change_text();
});
</script>
