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
        ## Order ref
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## Customer ref
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## PO ref
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## Supplier
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Doc. Status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## Line Status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## Received
        <Column ss:AutoFitWidth="1" ss:Width="54.75" />
        ## Requested Delivery Date
        <Column ss:AutoFitWidth="1" ss:Width="54.75" />
        ## order line
        <Column ss:AutoFitWidth="1" ss:Width="19.00" />
        ## product code
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## product description
        <Column ss:AutoFitWidth="1" ss:Width="239.25"  />
        ## Qty Ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## UoM Ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Qty Delivered
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## UoM Delivered
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## Packing
        <Column ss:AutoFitWidth="1" ss:Width="60.25" />
        ## Qty to deliver
        <Column ss:AutoFitWidth="1" ss:Width="50.5" />
        ## Transport
        <Column ss:AutoFitWidth="1" ss:Width="55.00" />
        ## Transport file
        <Column ss:AutoFitWidth="1" ss:Width="55.75" />
        ## CDD
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## ETA
        <Column ss:AutoFitWidth="1" ss:Width="50" />
        ## RTS Date
        <Column ss:AutoFitWidth="1" ss:Width="50" />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header"><Data ss:Type="String">${_('FIELD ORDER FOLLOW-UP FINANCE')|x}</Data><NamedCell ss:Name="Print_Area"/></Cell>
        </Row>

        <Row ss:Height="10"></Row>

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Instance information')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Request parameters')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Name:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.instance_id.instance or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Partners:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue" ss:MergeAcross="2"><Data ss:Type="String">${', '.join([p.name for p in o.partner_ids]) or '-'|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Address:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${o.company_id.partner_id.name or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date start:')|x}</Data></Cell>
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
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date end:')|x}</Data></Cell>
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
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date of the request:')|x}</Data></Cell>
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
                _('STV/IVO number'),
                _('STV/IVO line number'),
                _('STV/IVO line description'),
                _('STV/IVO line unit price'),
                _('STV/IVO line quantity'),
                _('STV/IVO line expense account code'),
                _('STV/IVO line sub total'),
                _('STV/IVO currency'),
                _('STV/IVO line sub total functional currency'),
                _('STV/IVO status'),
                _('Reverse corresponding AJI? (STV/IVO)'),
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
                % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
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
