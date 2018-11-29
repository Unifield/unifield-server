<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
    <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
        <Author>MSF</Author>
        <LastAuthor>MSF</LastAuthor>
        <Created>${time.strftime('%Y-%m-%dT%H:%M:%SZ')|x}</Created>
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
        <Style ss:ID="line_header">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
            <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000" ss:Bold="1" />
            <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
            <Borders>
                <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
        </Style>
        <Style ss:ID="line">
            <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
            <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000" ss:Bold="0" />
            <Borders>
                <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
        </Style>
        <Style ss:ID="line_short_date">
            <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
            <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000" ss:Bold="0" />
            <Borders>
                <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
                <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
            </Borders>
            <NumberFormat ss:Format="General Date"/>
        </Style>
    </Styles>
    % for o in objects:
    <ss:Worksheet ss:Name="${o.default_code|x}">
        <Table>
            <Column ss:AutoFitWidth="1" ss:Width="120" />
            <Column ss:AutoFitWidth="1" ss:Width="120" />
            <Column ss:AutoFitWidth="1" ss:Width="120" />
            <Column ss:AutoFitWidth="1" ss:Width="120" />
            <Column ss:AutoFitWidth="1" ss:Width="120" />
            <Column ss:AutoFitWidth="1" ss:Width="120" />

            <Row>
                <Cell ss:StyleID="line_header" ss:MergeAcross="1">
                    <Data ss:Type="String">${_('Product code')}</Data>
                </Cell>
                <Cell ss:StyleID="line" ss:MergeAcross="3">
                    <Data ss:Type="String">${o.default_code|x}</Data>
                </Cell>
            </Row>
            <Row>
                <Cell ss:StyleID="line_header" ss:MergeAcross="1">
                    <Data ss:Type="String">${_('Product description')}</Data>
                </Cell>
                <Cell ss:StyleID="line" ss:MergeAcross="3">
                    <Data ss:Type="String">${o.name|x}</Data>
                </Cell>
            </Row>

            <!-- Empty row -->
            <Row></Row>

            <Row>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('Date')}</Data>
                </Cell>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('User')}</Data>
                </Cell>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('Old Cost Price')}</Data>
                </Cell>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('New Cost Price')}</Data>
                </Cell>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('Transaction')}</Data>
                </Cell>
                <Cell ss:StyleID="line_header">
                    <Data ss:Type="String">${_('Manually changed (at reception)')}</Data>
                </Cell>
            </Row>
            % for sptc in getSPTC(o.id):
            <Row>
                % if isDateTime(sptc.change_date):
                <Cell ss:StyleID="line_short_date">
                    <Data ss:Type="DateTime">${sptc.change_date.replace(' ', 'T')|n}.000</Data>
                </Cell>
                % else:
                <Cell ss:StyleID="line_short_date">
                    <Data ss:Type="String"></Data>
                </Cell>
                % endif
                <Cell ss:StyleID="line">
                    <Data ss:Type="String">${sptc.user_id.name|x}</Data>
                </Cell>
                <Cell ss:StyleID="line">
                    <Data ss:Type="Number">${sptc.old_standard_price|x}</Data>
                </Cell>
                <Cell ss:StyleID="line">
                    <Data ss:Type="Number">${sptc.new_standard_price|x}</Data>
                </Cell>
                <Cell ss:StyleID="line">
                     % if sptc.transaction_name == 'Product creation':
                        <Data ss:Type="String">${_('Product creation')|x}</Data>
                     % else:
                    <Data ss:Type="String">${sptc.transaction_name or ''|x}</Data>
                    % endif
                </Cell>
                <Cell ss:StyleID="line">
                    <Data ss:Type="String">${sptc.in_price_changed and 'X' or ''|x}</Data>
                </Cell>
            </Row>
            % endfor-->
        </Table>
        <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
        </WorksheetOptions>
    </ss:Worksheet>
    % endfor
</Workbook>
