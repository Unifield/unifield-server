<input id="${name}" name="${name}" type="hidden"/>
<p id="sig_${name}" />
<table class="fields">
    <tr>
    <td class="item">
        <input id="${name}_txt" type="text" />
    </td>
    <td class="item">
        <button id="${name}_set_txt" type="button">Add text</button>
    </td>
    </tr>
</table>
<div>
    <button id="${name}_clear" type="button">Clear Signature</button>
</div>


<script>
$('#sig_${name}').signature({syncField: '#${name}'});
$('#sig_${name}').signature('option', 'syncFormat', 'PNG');
</script>

<script>
$('#${name}_set_txt').click(function() {
  var txt = $('#${name}_txt').val();
  $('#sig_${name}').signature('setText', txt);
});

$('#${name}_clear').click(function() {
    $('#sig_${name}').signature('clear');
});
</script>
