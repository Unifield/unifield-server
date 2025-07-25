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
    <!-- ssCells -->
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
    </Style>

    <!-- title -->
    <Style ss:ID="title">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="13"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="8"/>
    </Style>
    <Style ss:ID="header_blue">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="NoPack">
       <Alignment ss:Vertical="Center"/>
       <Font ss:FontName="Arial-Bold" x:Family="Swiss" ss:Size="13" ss:Color="#FF0000"/>
    </Style>
    <Style ss:ID="line_header">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="8"/>
        <Interior ss:Color="#BFBFBF" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_header_italic">
        <Alignment ss:Horizontal="Left" ss:Vertical="Top"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Italic="1" ss:Size="6"/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="6" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date"/>
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="6" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom" ss:WrapText="1"/>
        <NumberFormat ss:Format="Short Date" />
        <Font ss:FontName="Arial" x:Family="Swiss" ss:Size="8" ss:Color="#0000FF"/>
    </Style>
 </Styles>

% for ship in objects:
<Worksheet ss:Name="${ship.name.replace('/', '_')|x}">
  <Table x:FullColumns="1" x:FullRows="1" ss:DefaultRowHeight="15">
    <Column ss:AutoFitWidth="0" ss:Width="27"/>
    <Column ss:AutoFitWidth="0" ss:Width="59.25"/>
    <Column ss:AutoFitWidth="0" ss:Width="170"/>
    <Column ss:AutoFitWidth="0" ss:Width="99"/>
    <Column ss:Index="6" ss:AutoFitWidth="0" ss:Width="111.75"/>
    <Column ss:AutoFitWidth="0" ss:Width="130.75"/>
    <Column ss:AutoFitWidth="0" ss:Width="50.00"/>
    <Column ss:AutoFitWidth="0" ss:Width="89.25"/>
    <Column ss:AutoFitWidth="0" ss:Width="30"/>
    <Column ss:AutoFitWidth="0" ss:Width="30"/>
    <Column ss:AutoFitWidth="0" ss:Width="30"/>

    % for p in getPackingList(ship):
       <Row ss:Height="16.5">
         <Cell ss:StyleID="title"><Data ss:Type="String">${_('PACKING LIST')|x}</Data></Cell>
       </Row>
       <Row>
         <Cell>< ss:StyleID="header" Data ss:Type="String">${(p['ppl'].name)|x}</Data></Cell>
         <Cell ss:Index="10"><Data ss:Type="String"></Data></Cell>
       </Row>
       <Row></Row>
       <Row ss:AutoFitHeight="0">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Your Ref.:')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.client_order_ref or '-')|x}</Data></Cell>
         <Cell ss:StyleID="header"><Data ss:Type="String">${_('Shipper:')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"><Data ss:Type="String">${_('Consignee:')|x}</Data></Cell>
         <Cell ss:StyleID="header"><Data ss:Type="String">${_('Dispatch:')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"><Data ss:Type="String">${_('Invoice to:')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Our Ref.:')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.name or '-')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_name or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_name or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_id.name or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Supplier Packing List')|x}:</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].packing_list or '-')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_contact or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_contact or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.name or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('FO Date:')|x}</Data></Cell>
         % if p['ppl'].sale_id and isDate(p['ppl'].sale_id.date_order):
         <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${p['ppl'].sale_id.date_order|n}T00:00:00.000</Data></Cell>
         % else:
         <Cell ss:StyleID="header"><Data ss:Type="String"></Data></Cell>
         % endif
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_address or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_contact or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.street or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Packing date:')|x}</Data></Cell>
         % if p['ppl'].date and isDate(p['ppl'].date[0:10]):
         <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${p['ppl'].date[0:10]|n}T00:00:00.000</Data></Cell>
         % else:
         <Cell ss:StyleID="header"><Data ss:Type="String"></Data></Cell>
         % endif
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_phone or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_phone or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.street2 or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('RTS date:')|x}</Data></Cell>
         % if ship.shipment_expected_date and isDate(ship.shipment_expected_date[0:10]):
         <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${ship.shipment_expected_date[0:10]|n}T00:00:00.000</Data></Cell>
         % else:
         <Cell ss:StyleID="header_blue"><Data ss:Type="String"></Data></Cell>
         % endif
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_phone or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_phone or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.street2 or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Transport mode:')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(getSel(ship, 'transport_type'))|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.consignee_other or '')|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.zip or '')|x} ${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.city or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"><Data ss:Type="String">${_('Transport mode')|x}:</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(getSel(ship, 'transport_type'))|x}</Data></Cell>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(ship.shipper_other or '')|x}</Data></Cell>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id.country_id and p['ppl'].sale_id.partner_shipping_id.country_id.name or '')|x}</Data></Cell>
       </Row>
       <Row ss:AutoFitHeight="0" ss:Height="12">
         <Cell ss:MergeAcross="1" ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header"/>
         <Cell ss:StyleID="header_blue"><Data ss:Type="String">${(p['ppl'].sale_id and p['ppl'].sale_id.partner_shipping_id and (p['ppl'].sale_id.partner_shipping_id.phone or p['ppl'].sale_id.partner_shipping_id.mobile) or '')|x}</Data></Cell>
       </Row>

       % if not p['pf']:
       <Row>
           <Cell ss:StyleID="NoPack" ss:MergeAcross="11"><Data ss:Type="String">${_('NO PACK FAMILIES IN THIS PPL')|x}</Data></Cell>
       </Row>
       % endif
       % for pf in getParcel(p['pf']):
           <Row>
             <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Parcel No:')|x} ${(pf.from_pack)|x} ${_('to')|x} ${(pf.to_pack)|x}</Data></Cell>
             <Cell ss:StyleID="line_header"><Data ss:Type="String">${(pf.num_of_packs)|x} ${_('Parcel')|x}${(pf.num_of_packs > 1 and 's' or '')|x}</Data></Cell>
             <Cell ss:StyleID="line_header" ss:MergeAcross="3"><Data ss:Type="String">${_('Total weight')|x} ${(formatLang(pf.total_weight or 0.00))|x} kg     -     ${_('Total volume')|x} ${(formatLang(pf.total_volume or 0.00))|x} dm³</Data></Cell>
             <Cell ss:StyleID="line_header"/>
             <Cell ss:StyleID="line_header"/>
             <Cell ss:StyleID="line_header" ss:MergeAcross="2"><ss:Data ss:Type="String">${_('Containing:')|x}</Font></ss:Data></Cell>
           </Row>
           <Row ss:AutoFitHeight="0" ss:Height="17.25">
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Item')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic" ss:MergeAcross="2"><Data ss:Type="String">${_('Comment')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Total Qty.')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Batch')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('Exp. Date')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('CC')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('DG')|x}</Data></Cell>
             <Cell ss:StyleID="line_header_italic"><Data ss:Type="String">${_('CS')|x}</Data></Cell>
           </Row>
           % for m in pf.move_lines:
               <Row ss:AutoFitHeight="0" ss:Height="11.0625">
                   <Cell ss:StyleID="line_left"><Data ss:Type="Number">${(m.line_number)|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.product_id.default_code)|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.product_id.name)|x}</Data></Cell>
                   <Cell ss:StyleID="line_left" ss:MergeAcross="2"><Data ss:Type="String">${(m.comment or '')|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(formatLang(m.product_qty or 0.00))|x} ${(m.product_uom.name)|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.prodlot_id.name or '')|x}</Data></Cell>
                   % if isDate(m.prodlot_id.life_date):
                   <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${(m.prodlot_id.life_date)|n}T00:00:00.000</Data></Cell>
                   % else:
                   <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                   % endif
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.product_id.is_kc and 'X' or '')|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.product_id.dg_txt or '')|x}</Data></Cell>
                   <Cell ss:StyleID="line_left"><Data ss:Type="String">${(m.product_id.cs_txt or '')|x}</Data></Cell>
              </Row>
          % endfor
      % endfor
    %endfor
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Header x:Margin="0.3"/>
    <Footer x:Margin="0.3"/>
    <PageMargins x:Bottom="0.75" x:Left="0.7" x:Right="0.7" x:Top="0.75"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>0</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>33</ActiveRow>
     <ActiveCol>4</ActiveCol>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
  </WorksheetOptions>
 </Worksheet>
% endfor
</Workbook>
