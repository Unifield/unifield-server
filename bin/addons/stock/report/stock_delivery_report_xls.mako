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
  <Created>2014-04-16T22:36:07Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
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

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font ss:Size="13" ss:Bold="1" />
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="13" ss:Bold="1" />
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_header_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Lines -->
     <Style ss:ID="line">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#0"/>
    </Style>
    <Style ss:ID="line_center_nb">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date" />
    </Style>
    <Style ss:ID="general_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="General Date" />
    </Style>
 </Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Deliveries Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Reference
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Reason Type
        <Column ss:AutoFitWidth="1" ss:Width="115.0" />
        ## SHIP
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Origin
        <Column ss:AutoFitWidth="1" ss:Width="140.0" />
        ## Partner
        <Column ss:AutoFitWidth="1" ss:Width="110.0" />
        ## Order Type
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Order Category
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Order Priority
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Line
        <Column ss:AutoFitWidth="1" ss:Width="30.0" />
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="240.0" />
        ## UoM
        <Column ss:AutoFitWidth="1" ss:Width="40.0" />
        ## Qty
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Batch Number
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Expiry Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="45.0" />
        ## Total Currency
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Source Location
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Destination Location
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Actual Pack Date
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## Actual Shipped Date
        <Column ss:AutoFitWidth="1" ss:Width="120.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('DELIVERIES REPORT')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.company_id and r.company_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.report_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.report_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('FILTERS')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Date from')|x}</Data></Cell>
            % if r.start_date and isDate(r.start_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.start_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Date to')|x}</Data></Cell>
            % if r.end_date and isDate(r.end_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.end_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Partner')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.partner_id and r.partner_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Product Main Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.nomen_manda_0 and r.nomen_manda_0.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Source Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.location_id and r.location_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Destination Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.location_dest_id and r.location_dest_id.name or ''|x}</Data></Cell>
        </Row>

        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Reference'),
            _('Reason Type'),
            _('SHIP'),
            _('Origin'),
            _('Partner'),
            _('Order Type'),
            _('Order Category'),
            _('Order Priority'),
            _('Line'),
            _('Product Code'),
            _('Product Description'),
            _('UoM'),
            _('Qty'),
            _('Batch Number'),
            _('Expiry Date'),
            _('Unit Price'),
            _('Currency'),
            _('Total Currency'),
            _('Source Location'),
            _('Destination Location'),
            _('Actual Pack Date'),
            _('Actual Shipped Date'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for move in sorted(getMoves(r.moves_ids), key=lambda x: (x['shipped_date'] or '', x['ref'] or '', x['line_num'], x['prod_code'])):
            <Row ss:Height="12.0">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['ref']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['reason_type']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['ship']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['origin']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['partner']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['fo'] and getSel(move['fo'], 'order_type') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['header'] and getSel(move['header'], 'order_category') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['fo'] and getSel(move['fo'], 'priority') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['line_num']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['prod_code']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['prod_desc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['prod_uom']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${move['qty']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['prodlot']|x}</Data></Cell>
                % if move['expiry_date'] and isDate(move['expiry_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['expiry_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['price']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['total_currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['location']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['destination']|x}</Data></Cell>
                % if move['create_date'] and isDateTime(move['create_date']):
                <Cell ss:StyleID="general_date"><Data ss:Type="DateTime">${move['create_date'][:10]|n}T${move['create_date'][-8:]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if move['shipped_date'] and isDateTime(move['shipped_date']):
                <Cell ss:StyleID="general_date"><Data ss:Type="DateTime">${move['shipped_date'][:10]|n}T${move['shipped_date'][-8:]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
