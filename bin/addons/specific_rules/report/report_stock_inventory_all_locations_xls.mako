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
  <Style ss:ID="mainheader">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
        <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000"/>
        <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>

    <Style ss:ID="poheader">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#d3d3d3" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>

    <Style ss:ID="sumline">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#cecece" ss:Pattern="Solid"/>
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
    
  <Style ss:ID="poheader_short_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
  <Style ss:ID="short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
</Styles>

<ss:Worksheet ss:Name="Inventory Level all Locations">
## definition of the columns' size
<% locations = getLocations() %>
<% nb_of_columns = 5 + len(locations) %>
<Table x:FullColumns="1" x:FullRows="1">
    # Product code
    <Column ss:AutoFitWidth="1" ss:Width="81" />
    # Product Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # UoM
    <Column ss:AutoFitWidth="1" ss:Width="55" />
    # Batch
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Exp Date
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    % for loc in locations:
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    % endfor
    <Column ss:AutoFitWidth="1" ss:Width="80" />

% for o in objects:

    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${_('DB/instance name')}</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.company_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${_('Generated on')}</Data></Cell>
        % if o.name and isDateTime(o.name):
            <Cell ss:MergeAcross="2" ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.name[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="2" ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row></Row>
    <Row></Row>
    <%  total_value, nb_items, lines = getLines() %>
    <Row>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Total Value:</Data></Cell>
        <Cell ss:StyleID="sumline"><Data ss:Type="Number">${total_value}</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Nb Items withj qty>0:</Data></Cell>
        <Cell ss:StyleID="sumline"><Data ss:Type="Number">${nb_items}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Batch')}</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Exp Date')}</Data></Cell>
        % for loc in locations:
            <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Qty')}: ${loc.name|x}</Data></Cell>
        % endfor
        <Cell ss:StyleID="poheader"><Data ss:Type="String">${_('Total Qty')}</Data></Cell>
    </Row>

    % for prd in lines:
        % for line in prd['lines'].itervalues():
          % if line['qty'] or prd['with_product_list']:
          <Row ss:AutoFitHeight="1">
            <Cell ss:StyleID="line"><Data ss:Type="String">${(prd['product_code'])|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${(prd['product_name'])|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${(prd['uom'])|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${(line['batch'])|x}</Data></Cell>
            % if isDate(line['expiry_date']):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(line['expiry_date'])|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
            % endif
            % for loc in locations:
            <Cell ss:StyleID="line"><Data ss:Type="Number">${line['location_ids'].get(loc.id, 0.00)|x}</Data></Cell>
            % endfor
            <Cell ss:StyleID="sumline"><Data ss:Type="Number">${line.get('qty', 0.00)|x}</Data></Cell>
          </Row>
          %endif
        % endfor
    % endfor
 % endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
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
