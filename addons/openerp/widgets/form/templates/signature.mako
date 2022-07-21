<input id="${name}" name="${name}" type="hidden"/>
<p id="sig_${name}" />
<table class="fields">
    <tr>
    <td class="item">
        <input id="${name}_txt" type="text" />
    </td>
    <td class="item">
        <select id="${name}_posY">
            <option value="top">top</option>
            <option value="middle">middle</option>
            <option value="bottom" selected="selected">bottom</option>
        </select>
    </td>
    <td>
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
  var posY = $('#${name}_posY').val();
  $('#sig_${name}').signature('setText', txt, posY);
});

$('#${name}_clear').click(function() {
    $('#sig_${name}').signature('clear');
});
</script>
