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
    <Style ss:ID="short_date_header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
        <NumberFormat ss:Format="Short Date" />
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
    <Style ss:ID="line_center_grey">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
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
 </Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Expired/Damaged Products Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Reference
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Reason Type
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Product Main Type
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
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
        ## Total Price
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Source Location
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Destination Location
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Creation Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Actual Move Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Expired/Damaged Products Report')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String">${r.company_id and r.company_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.name):
            <Cell ss:StyleID="short_date_header" ss:MergeAcross="2"><Data ss:Type="DateTime">${parseDateXls(r.name)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Start date')|x}</Data></Cell>
            % if r.date_from and isDate(r.date_from):
            <Cell ss:StyleID="short_date_header" ss:MergeAcross="2"><Data ss:Type="DateTime">${parseDateXls(r.date_from)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('End date')|x}</Data></Cell>
            % if r.date_to and isDate(r.date_to):
            <Cell ss:StyleID="short_date_header" ss:MergeAcross="2"><Data ss:Type="DateTime">${parseDateXls(r.date_to)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Specific Source Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String">${r.location_id and r.location_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Specific Destination Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String">${r.location_dest_id and r.location_dest_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Reason Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String">${getReasonTypesText()|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_center_grey" ss:MergeAcross="1"><Data ss:Type="String">${_('Product Main Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_header_center" ss:MergeAcross="2"><Data ss:Type="String">${r.nomen_manda_0 and r.nomen_manda_0.name or ''|x}</Data></Cell>
        </Row>

        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Reference'),
            _('Reason Type'),
            _('Product Main Type'),
            _('Product Code'),
            _('Product Description'),
            _('UoM'),
            _('Qty'),
            _('Batch Number'),
            _('Expiry Date'),
            _('Unit Price'),
            _('Currency'),
            _('Total Price'),
            _('Source Location'),
            _('Destination Location'),
            _('Creation Date'),
            _('Actual Move Date'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for move in getMoves():
            <Row ss:Height="12.0">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['ref']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['reason_type']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['main_type']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['product_code']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['product_desc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['uom']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${move['qty']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['batch']|x}</Data></Cell>
                % if move['exp_date'] and isDate(move['exp_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['exp_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['unit_price']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['total_price']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['src_loc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['dest_loc']|x}</Data></Cell>
                % if move['crea_date'] and isDateTime(move['crea_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['crea_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if move['move_date'] and isDateTime(move['move_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['move_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
