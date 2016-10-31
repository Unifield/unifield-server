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
  <Style ss:ID="tab_content">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
  </Style>
</Styles>


<ss:Worksheet ss:Name="Stopped products">

  <Table x:FullColumns="1" x:FullRows="1">

    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product code
    <Columns ss:AutoFitWidth="1" ss:Width="200" /> # product description
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # product creator
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # standardization level
    <Columns ss:AutoFitWidth="1" ss:Width="90" /> # unidata status

    ##### Table with all stopped products #####
    
    <% bunker = get_uf_stopped_products() %>
    % for prod_id in bunker:
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Code</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Description</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Product Creator</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Standardization Level</Data></Cell>
          <Cell ss:StyleID="tab_header_orange"><Data ss:Type="String">Unidata Status</Data></Cell>
        </Row>

        <% standard_level = 'Standard' if bunker[prod_id].get('standardization_level') == 'True' else 'Non-standard' %>
        <Row ss:AutoFitHeight="1">
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(bunker[prod_id].get('product_code'))|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(bunker[prod_id].get('product_description'))|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(bunker[prod_id].get('product_creator'))|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(standard_level)|x}</Data></Cell>
          <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(bunker[prod_id].get('unidata_status') or '')|x}</Data></Cell>
        </Row>

        # instances linked to the current product :
        <% instances_data = bunker[prod_id].get('instances_data') %>
        % if len(instances_data) > 0:
            <Row ss:AutoFitHeight="1">
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Instance/Mission</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Unifield Status</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Instance stock</Data></Cell>
              <Cell ss:StyleID="tab_header_gray"><Data ss:Type="String">Pipeline Qty</Data></Cell>
            </Row>
            % for i in range(len(instances_data)):
                <Row ss:AutoFitHeight="1">
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(instances_data[i].get('instance_name'))|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="String">${(instances_data[i].get('unifield_status'))|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="Number">${(instances_data[i].get('instance_stock'))|x}</Data></Cell>
                  <Cell ss:StyleID="tab_content"><Data ss:Type="Number">${(instances_data[i].get('pipeline_qty'))|x}</Data></Cell>
                </Row>
            % endfor
            <Row></Row>
            <Row></Row>
        % endif
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
