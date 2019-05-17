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
    <Style ss:ID="line_bold">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <Font ss:Bold="1"/>
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
 </Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Products Situation Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Code
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## Description
        <Column ss:AutoFitWidth="1" ss:Width="250.0" />
        ## Uom
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Cost Price
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## Product Creator
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Creation Date
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Modification Date
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Real Stock
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Virtual Stock
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Available Stock
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## AMC
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## FMC
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="2"><Data ss:Type="String">${_('Products Situation Report')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.report_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.report_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
            %endif
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="line_bold"><Data ss:Type="String">${_('Filters')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Product Code:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.p_code or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Temperature sensitive item:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.heat_sensitive_item and r.heat_sensitive_item.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Product Description:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.p_desc or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Sterile:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'sterilized') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Main Type:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.nomen_manda_0 and r.nomen_manda_0.name or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Single Use:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'single_use') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Group:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.nomen_manda_1 and r.nomen_manda_1.name or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Controlled substance:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'controlled_substance') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Family:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.nomen_manda_2 and r.nomen_manda_2.name or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Dangerous goods:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'dangerous_goods') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Root:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.nomen_manda_3 and r.nomen_manda_3.name or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Expiry Date Mandatory:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'perishable') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('List:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.product_list_id and r.product_list_id.name or ''|x}</Data></Cell>
            <Cell></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Batch Number Mandatory:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(r, 'batch_management') or ''|x}</Data></Cell>
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Specified Stock Location:')|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${r.location_id and r.location_id.name or ''|x}</Data></Cell>
        </Row>

        <Row></Row>
        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Code'),
            _('Descrption'),
            _('UoM'),
            _('Cost Price'),
            _('Product Creator'),
            _('Creation Date'),
            _('Modification Date'),
            _('Real Stock'),
            _('Virtual Stock'),
            _('Available Stock'),
            _('AMC'),
            _('FMC'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for line in getLines(r):
            <Row ss:Height="12.0">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['code']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['uom']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${line['cost_price']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['creator']|x}</Data></Cell>
                % if line['create_date']:
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['create_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                %endif
                % if line['write_date']:
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(line['write_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                %endif
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['real_stock']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['virtual_stock']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['available_stock']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['amc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['fmc']|x}</Data></Cell>
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
