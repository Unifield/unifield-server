<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2012-06-18T15:46:09Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
<Styles>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
</Styles>
## ==================================== we loop over the composition_kit so "objects" == composition_kit  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s %s %s" % (o.composition_product_id and o.composition_product_id!='False' and o.composition_product_id.default_code.replace('/', '_') or '', o.composition_version_txt and o.composition_version_txt!='False' and o.composition_version_txt.replace('/', '_') or '', o.composition_creation_date and o.composition_creation_date!='False' and o.composition_creation_date.replace('/', '_') or '')|x}">

## definition of the columns' size
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="90" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="45" />
<Column ss:AutoFitWidth="1" ss:Width="200" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
<Column ss:AutoFitWidth="1" ss:Width="40" />
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Module')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Quantity')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UOM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('B.Num mandatory')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Exp. Date mandatory')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MML')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MSL')}</Data></Cell>
    </Row>
    ## we loop over the products line
    % for line in o.composition_item_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_module or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_product_id.default_code or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_product_id.name or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" >
            % if line.item_qty:
                <Data ss:Type="Number">${line.item_qty or 0|x}</Data>
            % else:
                <Data ss:Type="String"></Data>
            % endif
        </Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_uom_id.name or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.comment or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_product_id.batch_management and _('Y') or _('N')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.item_product_id.perishable and _('Y') or _('N')|x}</Data></Cell>
        ## <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(line, 'mml_status')|x}</Data></Cell>
        ## <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(line, 'msl_status')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
