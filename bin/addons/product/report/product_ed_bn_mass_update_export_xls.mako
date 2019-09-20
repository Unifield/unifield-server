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
    <Style ss:ID="ssCellBlue">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Color="#0000FF" />
    </Style>

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="10" />
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
        <Font x:Family="Swiss" ss:Size="10" ss:Bold="1"/>
        <Interior/>
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
        <Font ss:Size="10" />
        <NumberFormat ss:Format="#0"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10" />
        <NumberFormat ss:Format="#0"/>
    </Style>
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="10" />
        <NumberFormat ss:Format="#0"/>
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


% for r in objects:
<ss:Worksheet ss:Name="${_('Product BN/ED Mass Update Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Product code
        <Column ss:AutoFitWidth="1" ss:Width="150.00" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="250.00" />
        ## Old BN
        <Column ss:AutoFitWidth="1" ss:Width="50.00" />
        ## Old ED
        <Column ss:AutoFitWidth="1" ss:Width="50.00" />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('PRODUCT BN/ED MASS UPDATE REPORT')|x}</Data><NamedCell ss:Name="Print_Area"/></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Update Reference')|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${r.name|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Type of change')|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${getSel(r, 'type_of_bn_ed')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('Date of change')|x}</Data></Cell>
            % if r.date_of_change and isDateTime(r.date_of_change):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${r.date_of_change|n}00.000</Data></Cell>
            % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${_('User who Updated')|x}</Data></Cell>
            <Cell ss:StyleID="line_left"><Data ss:Type="String">${r.user_id.name|x}</Data></Cell>
        </Row>
        <Row></Row>

        ## WORKSHEET HEADER

        <%
        headers_list = [
                _('Product Code'),
                _('Product Description'),
                _('Old BN''),
                _('Old ED'),
            ]
        %>

        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for hist_line in getData(r.id):
            <Row>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${hist_line.default_code|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${hist_line.description|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${hist_line.old_bn and _('Yes') or _('No')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${hist_line.old_ed and _('Yes') or _('No')|x}</Data></Cell>
            </Row>
        % endfor
    </Table>

</ss:Worksheet>
% endfor
</Workbook>
