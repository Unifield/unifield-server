<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>Import Data</title>

    <link rel="stylesheet" type="text/css" href="/openerp/static/css/impex.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css?v=7.0"/>

    <script type="text/javascript">
        function import_results(detection) {
            jQuery('#records_data, #error, #imported_success').empty();

            // detect_data only returns the body part of this, or something
            var $detection = jQuery('<div>'+detection+'</div>');
            var $error = $detection.find('#error');
            if($error.children().length) {
                jQuery('#error')
                        .html($error.html());
                jQuery('#do_import').hide();
                return;
            }

            var $success = $detection.find('#imported_success');
            if($success.children().length) {
                jQuery('#imported_success')
                        .html($success.html());
                jQuery('#do_import').hide();
                jQuery('#table_format').hide();
                return;
            }
            jQuery('#do_import').show();
            jQuery('#records_data')
                    .html($detection.find('#records_data').html());
        }

        function do_import() {
            if(!jQuery('#csvfile').val()) { return; }
            jQuery('#import_data').attr({
                'action': openobject.http.getURL('/openerp/impex/import_data')
            }).ajaxSubmit({
                success: import_results
            });
        }

        function apply_changes() {
            ['csv_separator', 'csv_delimiter', 'csv_encoding'].forEach(function(e) {
                jQuery('#'+e).val(jQuery('#c_'+e).val())
            })

            autodetect_data()
        }
        function autodetect_data() {
            if(!jQuery('#csvfile').val()) { return; }
            jQuery('#import_data').attr({
                'action': openobject.http.getURL('/openerp/impex/detect_data')
            }).ajaxSubmit({
                success: import_results
            });

        }

        jQuery(document).ready(function () {
            if(!window.frameElement.set_title) { return; }
            // Set the page's title as title of the dialog
            var $header = jQuery('.pop_head_font');
            window.frameElement.set_title(
                $header.text());
            $header.closest('.side_spacing').parent().remove();
            jQuery('#csvfile').change(autodetect_data);

        });
    </script>

</%def>

<%def name="content()">
<form name="import_data" id="import_data" action="/openerp/impex/import_data" method="post" enctype="multipart/form-data">

    <input type="hidden" id="_terp_source" name="_terp_source" value="${source}"/>
    <input type="hidden" id="_terp_model" name="_terp_model" value="${model}"/>
    <input type="hidden" id="_terp_ids" name="_terp_ids" value="[]"/>
    <input type="hidden" id="_terp_fields2" name="_terp_fields2" value="[]"/>
    <input type="hidden" id="_terp_context" name="_terp_context" value="${ctx}"/>

    <table class="view" cellspacing="5" border="0" width="100%">
        <tr>
            <td class="side_spacing">
                <table width="100%" class="popup_header">
                    <tr>
                        <td align="center" class="pop_head_font">${_("Import Data")}</td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td class="side_spacing">
                <table width="100%">
                    <tr>
                        <td width="50%" valign="middle" for="" class=" item-separator">
                            <h2 class="separator horizontal">${_("1. Import a .CSV file")}</h2>
                        </td>
                        <td width="50%" valign="middle" for="" class=" item-separator">
                            <h2 class="separator horizontal">${_("2. CSV Options")}</h2>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            ${_("Select a .CSV file to import. If you need a sample of file to import,")}
                            ${_('you should use the export tool with the "Import Compatible" option.')}
                            <div>
                                <label for="csvfile">${_("CSV File:")}</label>
                                <input type="file" id="csvfile" size="50" name="csvfile"/>
                            </div>
                        </td>
                        <td>
                            <table>
                            <tr>
                                    <td class="label"><label for="c_csv_separator">${_("Separator:")}</label></td>
                                    <td><input type="text" size="1" name="c_csvsep" id="c_csv_separator" value=","/></td>
                                    <td class="label"><label for="c_csv_delimiter">${_("Delimiter:")}</label></td>
                                    <td><input type="text" size="1" name="c_csvdel" id="c_csv_delimiter" value='"'/></td>
                                    <td class="label"><label for="c_csv_encoding">${_("Encoding:")}</label></td>
                                    <td>
                                        <select name="csvcode" id="c_csv_encoding">
                                            <option value="utf-8">UTF-8</option>
                                            <option value="iso-8859-15">Latin 1</option>
                                            <option value="windows-1252">windows-1252</option>
                                            <option value="windows-1251">windows-1251</option>
                                        </select>
                                    </td>
                                <td class="label">
                                    <input type="hidden" name="csvsep" id="csv_separator" value=","/>
                                    <input type="hidden" name="csvdel" id="csv_delimiter" value='"'/>
                                    <input type="hidden" name="csv_encoding" id="csv_encoding" value="UTF-8" />
                                    <a class="button-a" href="javascript: void(0)" onclick="apply_changes();">${_("Apply changes")}</a>
                                </td>
                            </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td height="10px">
            </td>
        </tr>
        <tr>
            <td class="side_spacing" width="100%">
                <div id="record">
                    <table width="100%" id="table_format">
                        <tr>
                            <td width="100%" valign="middle" for="" class=" item-separator">
                                <h2 class="separator horizontal">${_("3. Check your file format")}</h2>
                            </td>
                        </tr>
                    </table>
                    <div id="error">
                        % if error:
                            <p style="white-space:pre-line;"
                                >${_("The import failed due to:\n %(message)s", message=error['message'])}</p>
                            % if 'preview' in error:
                                <p>${_("Here is a preview of the file we could not import:")}</p>
                                <pre>${error['preview']}</pre>
                            % endif
                        % endif
                    </div>
                    <table id="records_data" class="grid" width="100%" style="margin: 5px 0;">
                    % if records:
                        % for rownum, row in enumerate(records):
                            % if rownum == 0:
                                <tr class="grid-header">
                                    % for title in row:
                                      <th class="grid-cell">${title}</th>
                                    % endfor
                                 </tr>
                             % else:
                                 <tr class="grid-row">
                                    % for index, cell in enumerate(row):
                                      <td id="cell-${index}" name="cell" class="grid-cell">${cell}</td>
                                    % endfor
                                 </tr>
                             % endif
                        % endfor
                    % endif
                    </table>
                </div>
            </td>
        </tr>
        <tr id="imported_success">
            % if success:
            <td class="side_spacing">
                <table width="100%">
                    <tr>
                        <td width="100%" valign="middle" for="" class=" item-separator" colspan="4">
                            <h2 class="separator horizontal">${_("3. File imported")}</h2>
                        </td>
                    </tr>
                    <tr>
                        <td class="success">
                            ${success['message']}
                        </td>
                    </tr>
                </table>
            </td>
            % endif
        </tr>
        <tr>
            <td class="side_spacing">
                <table width="100%">
                    <tr>
                        <td class="imp-header" align="left">
                            <a class="button-a oe_form_button_cancel" href="javascript: void(0)" onclick="window.frameElement.close()">${_("Close")}</a>
                            <a class="button-a" id="do_import" href="javascript: void(0)" onclick="do_import();" style="display: none;">${_("Import File")}</a>
                        </td>
                        <td width="5%"></td>
                </table>
            </td>
        </tr>
    </table>
</form>
</%def>
