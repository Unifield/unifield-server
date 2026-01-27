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
        <Font x:Family="Swiss" ss:Size="13" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="9" />
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
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
     <Style ss:ID="line_left">
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
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center_gray">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
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

<ss:Worksheet ss:Name="${_('Reserved Product Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Customer/Location Requestor
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## IR/FO Reference
        <Column ss:AutoFitWidth="1" ss:Width="145.25" />
        ## Customer Reference
        <Column ss:AutoFitWidth="1" ss:Width="145.25" />
        ## Order Details
        <Column ss:AutoFitWidth="1" ss:Width="200.0" />
        ## Source Location
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="145.25" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="260.25" />
        ## UoM
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## Batch
        <Column ss:AutoFitWidth="1" ss:Width="75.25" />
        ## Expiry Date
        <Column ss:AutoFitWidth="1" ss:Width="75.25" />
        ## Reserved Qty
        <Column ss:AutoFitWidth="1" ss:Width="80.25" />
        ## Reserved Document
        <Column ss:AutoFitWidth="1" ss:Width="145.25" />
        ## Total Ordered Qty
        <Column ss:AutoFitWidth="1" ss:Width="85.0" />
        ## Total Reserved Qty
        <Column ss:AutoFitWidth="1" ss:Width="85.0" />
        ## Total Reserved Value
        <Column ss:AutoFitWidth="1" ss:Width="85.0" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## PO Reference
        <Column ss:AutoFitWidth="1" ss:Width="145.25" />

        ## WORKSHEET HEADER

        ${initData()}

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('RESERVED PRODUCTS REPORT')|x}</Data></Cell>
        </Row>

        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${getInstanceName()|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${getDate()|x}</Data></Cell>
        </Row>

        <Row></Row>

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header"><Data ss:Type="String">${_('FILTERS')|x}</Data></Cell>
        </Row>

        <Row>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${_('Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${getLoc() or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${_('Product Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${getProd() or ''|x}</Data></Cell>
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Customer/Location Requestor')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('IR/FO Reference')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Customer Reference')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Order Details')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Source Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Product Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Product Description')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('UoM')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Batch')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Expiry Date')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Reserved Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Reserved Document')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Ordered Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Reserved Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Reserved Value')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Currency')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('PO Reference')|x}</Data></Cell>
        </Row>

        % for line in getLines():
            <Row ss:Height="12.0">
                % if line['sum_line']:
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${line['loc_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${line['prod_name'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${line['prod_desc'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${line['prod_uom']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="Number">${line['sum_ordered_qty'] or 0.00|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="Number">${line['sum_qty'] or 0.00|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="Number">${line['sum_value'] or 0.00|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${line['currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_gray"><Data ss:Type="String">${''|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['origin'] or line['partner_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['so_name'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['customer_ref'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['so_details']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['loc_name']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['prod_name'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['prod_desc'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['prod_uom']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['batch']|x}</Data></Cell>
                    % if isDate(line['exp_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['exp_date']|x}</Data></Cell>
                    % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
                    % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line['prod_qty'] or 0.00|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['documents'] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line['po_name']|x}</Data></Cell>
                % endif
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
</Workbook>
