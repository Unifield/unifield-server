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
  <Style ss:ID="tab_header_orange">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_header_gray">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#dbdbdb" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_content0">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_content1">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
  <Style ss:ID="tab_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="Short Date"/>
  </Style>
</Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Stock & Pipe per Product and per Instance')|x}">

  <Table x:FullColumns="1" x:FullRows="1">

    # Product Code
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # Product Creator
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Standardization Level
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # UniData Status
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # HQ UniField Status
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Instance/Mission
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # Instance UniField Status
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Instance stock
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Pipeline Qty
    <Column ss:AutoFitWidth="1" ss:Width="90" />

    ##### Table with all products #####
    <Row>
        <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Report Date')}:</Data></Cell>
        <Cell ss:StyleID="tab_date"><Data ss:Type="DateTime">${parseDateXls(r.name)|n}</Data></Cell>
    </Row>
    <Row></Row>
    <% products = get_products() %>
    % if not products:
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_content0" ss:MergeAcross="1"><Data ss:Type="String">${_('There are no products to report')|x}</Data></Cell>
        </Row>
    % endif

    <Row ss:AutoFitHeight="1">
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Product Creator')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('Standardization Level')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('UniData Status')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">${_('HQ UniField Status')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${_('Instance/Mission')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${_('Instance UniField Status')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${_('Instance stock')|x}</Data></Cell>
      <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">${_('Pipeline Qty')|x}</Data></Cell>
    </Row>

    <% i = 1 %>
    % for prod in products:
        <% i = 1 - i %>
        <% smrl_list = get_stock_mission_report_lines(r, prod) %>
        % for smrl in smrl_list:
            <Row ss:AutoFitHeight="1">
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${prod[1]|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${prod[2]|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${prod[3] or ''|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${getSelValue('product.product', 'standard_ok', smrl[7]) or ''|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${getSelValue('product.product', 'state_ud', smrl[8]) or ''|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${get_product_state(smrl[9])|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${smrl[1]|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="String">${get_product_state(smrl[6])|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="Number">${smrl[4]|x}</Data></Cell>
              <Cell ss:StyleID="tab_content${i}"><Data ss:Type="Number">${smrl[5]|x}</Data></Cell>
            </Row>
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
% endfor

</Workbook>
