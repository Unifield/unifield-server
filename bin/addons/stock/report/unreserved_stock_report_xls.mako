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
        <Font x:Family="Swiss" ss:Size="8" ss:Bold="1"/>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
        <Interior/>
    </Style>

    <!-- Lines -->
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center_gray">
        <Alignment ss:Horizontal="Center" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
        <Interior/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
    </Style>
</Styles>

% for r in objects:
<ss:Worksheet ss:Name="Unreserved Stock Excel Export">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Location
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Product code
        <Column ss:AutoFitWidth="1" ss:Width="70.25" />
        ## Product description
        <Column ss:AutoFitWidth="1" ss:Width="250.25" />
        ## UoM
        <Column ss:AutoFitWidth="1" ss:Width="58.75" />
        ## Batch Number
        <Column ss:AutoFitWidth="1" ss:Width="70.25" />
        ## Expiration Date
        <Column ss:AutoFitWidth="1" ss:Width="70.25" />
        ## Unreserved Qty
        <Column ss:AutoFitWidth="1" ss:Width="75.25" />
        ## Total Unreserved
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('UNRESERVED STOCK REPORT')|x}</Data></Cell>
        </Row>

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center_gray"><Data ss:Type="String"></Data>${getInstanceName()|x}</Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            <Cell ss:StyleID="short_date"><Data ss:Type="String">${getDate()|x}</Data></Cell>
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Product Code')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Product Description')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('UoM')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Batch Number')|x}</Data></Cell>
            <Cell ss:StyleID="short_date"><Data ss:Type="String">${_('Expiration Date')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Unreserved Qty')|x}</Data></Cell>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Total Unreserved')|x}</Data></Cell>
        </Row>

        % for line in getUnreservedMovesData:
            <Row ss:Height="11.25">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[0]|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[1] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${line[2] or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[3]|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[4] or '-'|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[5] or '-'|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[6] or 0.00|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line[7] or 0.00|x}</Data></Cell>
            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
