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
  <Style ss:ID="mainheader_short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
  <Style ss:ID="mainheader_date_hour">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="dd/mm/yyyy\ hh:mm;@"/>
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

<ss:Worksheet ss:Name="Export Inventory Level">
## definition of the columns' size
<% nb_of_columns = 12 %>
<Table x:FullColumns="1" x:FullRows="1">
    # Product code
    <Column ss:AutoFitWidth="1" ss:Width="81" />
    # Product Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # UoM
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Batch
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Exp Date
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Qty
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Value
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Total Qty
    <Column ss:AutoFitWidth="1" ss:Width="120" />
    # Total Value
    <Column ss:AutoFitWidth="1" ss:Width="120" />

% for o in objects:

    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">DB/instance name</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.company_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Report Generation date</Data></Cell>
        % if o.name and isDateTime(o.name):
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader_date_hour" ><Data ss:Type="DateTime">${o.name[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Stock Level date</Data></Cell>
        % if o.stock_level_date and isDate(o.stock_level_date):
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader_date_hour" ><Data ss:Type="DateTime">${o.stock_level_date|n}T${'23:59:59'|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Specific product</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.product_id and o.product_id.default_code or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Specific Product list</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.product_list_id and o.product_list_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Specific batch</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.prodlot_id and o.prodlot_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Specific expiry date</Data></Cell>
        % if o.expiry_date and isDateTime(o.expiry_date):
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader_short_date" ><Data ss:Type="DateTime">${o.expiry_date|n}T00:00:00.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="2" ss:StyleID="mainheader" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">Specific location</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.location_id and o.location_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${_('Including products with stock <= 0 with movements in the last months')|x}</Data></Cell>
        <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${o.display_0 and 'True (' + o.in_last_x_months + ' months)' or 'False'|x}</Data></Cell>
    </Row>

    <% processed_lines = getLines() %>

    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Number of items with stock > 0</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Total value of the generated report</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Currency</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${getLinesAbove0()|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${getTotalValues()|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${o.company_id.currency_id.name|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Product Code</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Product Description</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">UoM</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Batch</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Exp Date</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Qty</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Value</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Total Qty</Data></Cell>
        <Cell ss:StyleID="poheader"><Data ss:Type="String">Total Value</Data></Cell>
    </Row>
    
    % for prd in processed_lines:
      % if prd['sum_qty'] or prd['with_product_list'] or display0InRange(o.display_0, o.name, o.stock_level_date, o.in_last_x_months, prd['date']):
      <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="sumline"><Data ss:Type="String">${(prd['product_code'])|x}</Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String">${(prd['product_name'])|x}</Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String">${(prd['uom'])|x}</Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="String"></Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="Number">${(round(prd['sum_qty'], 2))|x}</Data></Cell>
          <Cell ss:StyleID="sumline"><Data ss:Type="Number">${(round(prd['sum_value'], 2))|x}</Data></Cell>
      </Row>
        % for line in prd['lines'].itervalues():
          % if line['qty'] or prd['with_product_list'] or display0InRange(o.display_0, o.name, o.stock_level_date, o.in_last_x_months, prd['date']):
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
            <Cell ss:StyleID="line"><Data ss:Type="Number">${(round(line['qty'], 2))|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="Number">${(round(line['value'], 2))|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
          </Row>
          %endif
        % endfor
      % endif
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
