<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Unifield</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Company>Medecins Sans Frontieres</Company>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>11640</WindowHeight>
  <WindowWidth>15480</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>75</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellBlue">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Color="#0000FF" />
    </Style>

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="9" />
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="7" ss:Bold="1"/>
        <Interior/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_green">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#1A721A"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_date_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>

    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Font ss:Size="8" ss:Color="#0000FF" />
    </Style>
    <Style ss:ID="short_date_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
        <Font ss:Size="8" ss:Color="#0000FF" />
    </Style>

    <Style ss:ID="line_left_grey">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
    <Style ss:ID="line_right_grey">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center_grey">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date_grey">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
    <Style ss:ID="line_left_date_grey_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
</Styles>

<ss:Worksheet ss:Name="${_('FO Follow Up')|x}">
% for o in objects:
    <Table x:FullColumns="1" x:FullRows="1">

        ## FO number
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## Customer name
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## Customer ref
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## PO number
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## Supplier name
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## Supplier invoice number
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## SI line number
        <Column ss:AutoFitWidth="1" ss:Width="40.00"  />
        ## SI line description
        <Column ss:AutoFitWidth="1" ss:Width="300.00"  />
        ## SI line unit price
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## SI line quantity
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## SI line expense account code
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## SI line sub total
        <Column ss:AutoFitWidth="1" ss:Width="98.25"  />
        ## SI currency
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## SI line sub total functional currency
        <Column ss:AutoFitWidth="1" ss:Width="98.25"  />
        ## SI status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## Reverse corresponding AJI? (SI)
        <Column ss:AutoFitWidth="1" ss:Width="65.00"  />
        ## FO status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## FO line status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## FO line number
        <Column ss:AutoFitWidth="1" ss:Width="40.00"  />
        ## Product code
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## Product description
        <Column ss:AutoFitWidth="1" ss:Width="239.25"  />
        ## Qty ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## UoM ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Qty delivered
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## Transport file
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## STV/IVO number
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## STV/IVO line number
        <Column ss:AutoFitWidth="1" ss:Width="40.00"  />
        ## STV/IVO line description
        <Column ss:AutoFitWidth="1" ss:Width="300.00"  />
        ## STV/IVO line unit price
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## STV/IVO line quantity
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## STV/IVO line expense account code
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## STV/IVO line sub total
        <Column ss:AutoFitWidth="1" ss:Width="98.25"  />
        ## STV/IVO currency
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## STV/IVO line sub total functional currency
        <Column ss:AutoFitWidth="1" ss:Width="98.25"  />
        ## STV/IVO status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## Reverse corresponding AJI? (STV/IVO)
        <Column ss:AutoFitWidth="1" ss:Width="65.00"  />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header"><Data ss:Type="String">${_('FIELD ORDER FOLLOW-UP FINANCE')|x}</Data><NamedCell ss:Name="Print_Area"/></Cell>
        </Row>

        <Row ss:Height="10"></Row>

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Instance information')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="3"><Data ss:Type="String">${_('Request parameters')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Name:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.instance_id.instance or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Partners:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue" ss:MergeAcross="2"><Data ss:Type="String">${', '.join([p.name for p in o.partner_ids]) or '-'|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Address:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.partner_id.name or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Date start:')|x}</Data></Cell>
            % if isDate(o.start_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.start_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.start_date|n}T00:00:00.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.partner_id.address[0].street or ''|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Date end:')|x}</Data></Cell>
            % if isDate(o.end_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.end_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.end_date|n}T00:00:00.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.partner_id.address[0].zip|x} ${o.company_id.partner_id.address[0].city|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Date of the request:')|x}</Data></Cell>
            % if o.report_date and isDateTime(o.report_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.report_date[0:10]|n}T${o.report_date[11:19]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${o.report_date[0:10]|n}T${o.report_date[11:19]|n}.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>

        <Row></Row>

        <%
            is_intermission = context and context.get('is_intermission')
            header_list = [
                _('FO number'),
                _('Customer name'),
                _('Customer ref'),
                _('PO number'),
                _('Supplier name'),
                _('Supplier invoice number'),
                _('SI line number'),
                _('SI line description'),
                _('SI line unit price'),
                _('SI line quantity'),
                _('SI line expense account code'),
                _('SI line sub total'),
                _('SI currency'),
                _('SI line sub total functional currency'),
                _('SI status'),
                _('Reverse corresponding AJI? (SI)'),
                _('FO status'),
                _('FO line status'),
                _('FO line number'),
                _('Product code'),
                _('Product description'),
                _('Qty ordered'),
                _('UoM ordered'),
                _('Qty delivered'),
                _('Transport file'),
                is_intermission and _('IVO number') or _('STV number'),
                is_intermission and _('IVO line number') or _('STV line number'),
                is_intermission and _('IVO line description') or _('STV line description'),
                is_intermission and _('IVO line unit price') or _('STV line unit price'),
                is_intermission and _('IVO line quantity') or _('STV line quantity'),
                is_intermission and _('IVO line expense account code') or _('STV line expense account code'),
                is_intermission and _('IVO line sub total') or _('STV line sub total'),
                is_intermission and _('IVO currency') or _('STV currency'),
                is_intermission and _('IVO line sub total functional currency') or _('STV line sub total functional currency'),
                is_intermission and _('IVO status') or _('STV status'),
                is_intermission and _('Reverse corresponding AJI? (IVO)') or _('Reverse corresponding AJI? (STV)'),
            ]
        %>

        <Row>
        % for h in header_list:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for line in getReportLines(o):
            <Row ss:Height="11.25">
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['fo_number']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['customer_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['customer_reference']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['po_number']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['supplier_name']|x}</Data></Cell>
                % if line['si']:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_number']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_line_number']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_line_description']|x}</Data></Cell>
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['si_line_unit_price']|x}</Data></Cell>
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['si_line_quantity']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_line_account_code']|x}</Data></Cell>
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['si_line_subtotal']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_currency']|x}</Data></Cell>
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['si_line_subtotal_fctal']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['si_state']|x}</Data></Cell>
                    <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['reverse_aji_si']|x}</Data></Cell>
                % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['fo_status']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['fo_line_status']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['fo_line_number']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['product_code']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['product_description']|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['qty_ordered']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['uom_ordered']|x}</Data></Cell>
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['qty_delivered']|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['transport_file']|x}</Data></Cell>
                % if line['out_inv']:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_number']|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_line_number']|x}</Data></Cell>
                        <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_description']|x}</Data></Cell>
                        <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['out_inv_unit_price']|x}</Data></Cell>
                        <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['out_inv_quantity']|x}</Data></Cell>
                        <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_account_code']|x}</Data></Cell>
                        <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['out_inv_line_subtotal']|x}</Data></Cell>
                        <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_currency']|x}</Data></Cell>
                        <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line['out_inv_line_subtotal_fctal']|x}</Data></Cell>
                        <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['out_inv_state']|x}</Data></Cell>
                        <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['reverse_aji_out_inv']|x}</Data></Cell>
                % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
            </Row>
        % endfor

    </Table>
% endfor

<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <PageSetup>
        <Layout x:Orientation="Landscape"/>
        <Footer x:Data="Page &amp;P of &amp;N"/>
    </PageSetup>
    <Selected/>
    <Panes>
        <Pane>
            <Number>3</Number>
            <ActiveRow>17</ActiveRow>
        </Pane>
    </Panes>
    <ProtectObjects>False</ProtectObjects>
    <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</ss:Worksheet>
</Workbook>
