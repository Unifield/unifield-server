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
<ss:Worksheet ss:Name="${_('Supplier Performance Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Supplier
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## PO Reference
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## IN Reference
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## SI Reference
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Line number
        <Column ss:AutoFitWidth="1" ss:Width="55.0" />
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="250.0" />
        ## Status
        <Column ss:AutoFitWidth="1" ss:Width="55.0" />
        ## Qty Ordered
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Qty Received
        <Column ss:AutoFitWidth="1" ss:Width="65.0" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Catalogue Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## PO Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## IN Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## SI Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Discrepancy IN to PO
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Discrepancy SI to PO
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Catalogue Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## PO Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## IN Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## SI Unit Price (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Discrepancy IN to PO (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Discrepancy SI to PO (functional)
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## PO Creation Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Validation Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delivery Requested Date (RDD)
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delivery Confirmed Date (CDD)
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Physical Reception Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Days to validate
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Days to confirm
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## Delay b/w actual delivery and CDD (days)
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delay b/w actual delivery and RDD (days)
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Internal Lead Time (days PO creation to reception)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Actual Supplier Lead Time (days PO validation to reception)
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Configured Supplier Lead Time
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Discrepancy b/w actual Lead Time and Supplier Lead Time
        <Column ss:AutoFitWidth="1" ss:Width="75.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('DB/Instance Name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.company_id and r.company_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.report_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.report_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Supplier Name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.partner_id and r.partner_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Supplier Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('Purchase Order Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('From')|x}</Data></Cell>
            % if isDateTime(r.date_from):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.date_from)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${_('To')|x}</Data></Cell>
            % if isDateTime(r.date_to):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.date_to)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>

        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Supplier'),
            _('PO Reference'),
            _('IN Reference'),
            _('SI Reference'),
            _('Line number'),
            _('Product Code'),
            _('Product Description'),
            _('Status'),
            _('Qty Ordered'),
            _('Qty Received'),
            _('Currency'),
            _('Catalogue Unit Price'),
            _('PO Unit Price'),
            _('IN Unit Price'),
            _('SI Unit Price'),
            _('Discrepancy IN to PO'),
            _('Discrepancy SI to PO'),
            _('Catalogue Unit Price (functional)'),
            _('PO Unit Price (functional)'),
            _('IN Unit Price (functional)'),
            _('SI Unit Price (functional)'),
            _('Discrepancy IN to PO (functional)'),
            _('Discrepancy SI to PO (functional)'),
            _('PO Creation Date'),
            _('Validation Date'),
            _('Delivery Requested Date (RDD)'),
            _('Delivery Confirmed Date (CDD)'),
            _('Physical Reception Date'),
            _('Days to validate'),
            _('Days to confirm'),
            _('Delay b/w actual delivery and CDD (days)'),
            _('Delay b/w actual delivery and RDD (days)'),
            _('Internal Lead Time (days PO creation to reception)'),
            _('Actual Supplier Lead Time (days PO validation to reception)'),
            _('Configured Supplier Lead Time'),
            _('Discrepancy b/w actual Lead Time and Supplier Lead Time'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for line in getLines(r):
            <Row ss:Height="12.0">

            </Row>
        % endfor

    </Table>
</ss:Worksheet>
% endfor
</Workbook>
