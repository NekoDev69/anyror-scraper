"""
VF-7 HTML Report Generator - Matches AnyROR Portal Layout Exactly
"""

import json
import sys
import glob
import re
from datetime import datetime


class VF7ReportGenerator:
    """Generate HTML reports matching AnyROR portal layout"""
    
    def __init__(self):
        self.css = self._get_css()
    
    def _get_css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: Arial, sans-serif;
            background: #f0f0f0;
            padding: 20px;
            font-size: 13px;
        }
        .container {
            max-width: 1050px;
            margin: 0 auto;
            background: #f0f0f0;
        }
        
        /* Header Section */
        .header-section {
            background: #ffffcc;
            border: 2px solid #999;
            padding: 15px;
            margin-bottom: 10px;
        }
        .status-time {
            color: red;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .location-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 15px;
        }
        .location-item .label {
            font-weight: bold;
            color: #006600;
            font-size: 12px;
        }
        .location-item .value {
            color: #000;
            margin-top: 3px;
        }
        .upin-row {
            margin-top: 15px;
            padding-top: 10px;
        }
        .upin-label {
            font-weight: bold;
            color: #006600;
            font-size: 12px;
        }
        .upin-value {
            color: blue;
            font-weight: bold;
        }
        
        /* Land Details Section */
        .land-section {
            background: #ffffcc;
            border: 2px solid #999;
            padding: 15px;
            margin-bottom: 10px;
        }
        .section-title {
            font-weight: bold;
            color: #006600;
            margin-bottom: 15px;
            font-size: 13px;
        }
        .land-table {
            width: 100%;
        }
        .land-table td {
            padding: 5px 10px 5px 0;
            vertical-align: top;
        }
        .land-table .label {
            font-weight: bold;
            color: #000;
            white-space: nowrap;
        }
        .land-table .value {
            color: #000;
        }
        
        /* Tables Section */
        .tables-section {
            background: #ffffcc;
            border: 2px solid #999;
            padding: 15px;
            margin-bottom: 10px;
        }
        .tables-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .table-box {
            border: 1px solid #999;
            background: white;
        }
        .table-title {
            background: #ccffcc;
            padding: 8px 10px;
            font-weight: bold;
            border-bottom: 1px solid #999;
        }
        
        /* Ownership Table */
        .ownership-table {
            width: 100%;
            border-collapse: collapse;
        }
        .ownership-table th {
            background: #e6ffe6;
            padding: 8px;
            border: 1px solid #999;
            font-weight: bold;
            text-align: center;
            font-size: 12px;
        }
        .ownership-table td {
            padding: 8px;
            border: 1px solid #999;
            vertical-align: top;
        }
        .entry-numbers {
            color: #000;
            margin-bottom: 5px;
        }
        .separator-line {
            border-bottom: 1px dashed #999;
            margin: 5px 0;
        }
        .owner-line {
            margin: 3px 0;
        }
        .owner-line a {
            color: blue;
            text-decoration: underline;
        }
        
        /* Boja Table */
        .boja-table {
            width: 100%;
            border-collapse: collapse;
        }
        .boja-table th {
            background: #e6ffe6;
            padding: 8px;
            border: 1px solid #999;
            font-weight: bold;
            text-align: center;
            font-size: 12px;
        }
        .boja-table td {
            padding: 8px;
            border: 1px solid #999;
            vertical-align: top;
        }
        .boja-entry {
            margin: 8px 0;
            padding-bottom: 8px;
            border-bottom: 1px dashed #ccc;
        }
        .boja-entry:last-child {
            border-bottom: none;
        }
        
        /* Disclaimer */
        .disclaimer {
            padding: 15px;
            font-size: 12px;
            color: #666;
            text-align: center;
        }
        
        @media print {
            body { background: white; padding: 0; }
        }
        """
    
    def generate_html(self, data: dict) -> str:
        """Generate HTML report matching AnyROR layout"""
        
        location = data.get("location", {})
        property_id = data.get("property_identity", {})
        land = data.get("land_details", {})
        meta = data.get("meta", {})
        
        # Parse tables from raw data
        ownership_html = self._build_ownership_table(data)
        boja_html = self._build_boja_table(data)
        
        # Get area - fix incomplete extraction (must have 3 parts: H-A-M)
        area = land.get('total_area_raw', '')
        if not area or area.endswith('-') or area.count('-') < 2:
            area = self._extract_area_from_raw(data)
        
        html = f"""<!DOCTYPE html>
<html lang="gu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VF-7 - {location.get('village', {}).get('name_local', '')}</title>
    <style>{self.css}</style>
</head>
<body>
    <div class="container">
        
        <!-- Header with Location -->
        <div class="header-section">
            <div class="status-time">* તા.{meta.get('data_status_time_local', '')} ની સ્થિતિએ</div>
            
            <div class="location-grid">
                <div class="location-item">
                    <div class="label">District (જીલ્લો)</div>
                    <div class="value">{location.get('district', {}).get('name_local', '')}</div>
                </div>
                <div class="location-item">
                    <div class="label">Taluka (તાલુકો)</div>
                    <div class="value">{location.get('taluka', {}).get('name_local', '')}</div>
                </div>
                <div class="location-item">
                    <div class="label">Village (ગામ)</div>
                    <div class="value">{location.get('village', {}).get('name_local', '')}</div>
                </div>
                <div class="location-item">
                    <div class="label">Survey/ Block Number (સરવે/ બ્લોક નંબર)</div>
                    <div class="value">{property_id.get('survey_number', '')}</div>
                </div>
            </div>
            
            <div class="upin-row">
                <span class="upin-label">UPIN (Unique Property Identification Number)</span><br>
                <span class="upin-value">{property_id.get('upin', '')}</span>
            </div>
        </div>
        
        <!-- Land Details -->
        <div class="land-section">
            <div class="section-title">Land Details (જમીનની વિગતો)</div>
            
            <table class="land-table">
                <tr>
                    <td class="label">Total Area (H.Are.SqMt.) (કુલ ક્ષેત્રફળ હે.આરે.ચોમી.) :</td>
                    <td class="value">{area}</td>
                </tr>
                <tr>
                    <td class="label">Total Assessment Rs. (કુલ આકાર રૂ. ) :</td>
                    <td class="value">{land.get('assessment_tax', '')}</td>
                </tr>
                <tr>
                    <td class="label">Tenure (સત્તાપ્રકાર) :</td>
                    <td class="value">{land.get('tenure_local', '') or land.get('tenure', '')}</td>
                </tr>
                <tr>
                    <td class="label">Land Use (જમીનનો ઉપયોગ) :</td>
                    <td class="value">{land.get('land_use_local', '') or land.get('land_use', '')}</td>
                </tr>
                <tr>
                    <td class="label">Name of farm (ખેતરનું નામ) :</td>
                    <td class="value">{self._clean_field(land.get('farm_name', ''))}</td>
                </tr>
                <tr>
                    <td class="label">Other Details (રીમાર્ક્સ) :</td>
                    <td class="value">{self._clean_field(land.get('remarks', ''))}</td>
                </tr>
            </table>
        </div>
        
        <!-- Ownership and Boja Tables -->
        <div class="tables-section">
            <div class="tables-grid">
                <!-- Ownership Details -->
                <div class="table-box">
                    <div class="table-title">Ownership Details (ખાતેદારની વિગતો)</div>
                    {ownership_html}
                </div>
                
                <!-- Boja and Other Rights -->
                <div class="table-box">
                    <div class="table-title">Boja and Other Rights Details (બોજા અને બીજા હક્ક ની વિગતો)</div>
                    {boja_html}
                </div>
            </div>
        </div>
        
        <!-- Disclaimer -->
        <div class="disclaimer">
            * અહીં દર્શાવેલ જમીનની વિગતો ફક્ત આપની જાણ માટે જ છે જેને સત્તાવાર નકલ તરીકે ગણવામાં આવશે નહી.
        </div>
        
    </div>
</body>
</html>"""
        
        return html
    
    def _clean_field(self, value: str) -> str:
        """Clean field value - remove garbage"""
        if not value:
            return ''
        # Remove if contains section headers
        bad_words = ['Ownership', 'Details', 'Other Details', 'રીમાર્ક્સ', 'ખાતેદારની']
        for word in bad_words:
            if word in value:
                return ''
        return value
    
    def _extract_area_from_raw(self, data: dict) -> str:
        """Extract area from raw page text"""
        raw = data.get('raw_page_text_backup', '')
        
        # Try to find area in format X-XX-XX (including પ which is used as 5)
        match = re.search(r'([૦-૯પ0-9]+-[૦-૯પ0-9]+-[૦-૯પ0-9]+)', raw)
        if match:
            return match.group(1)
        
        return ''
    
    def _build_ownership_table(self, data: dict) -> str:
        """Build ownership table with proper two-column format"""
        raw = data.get('raw_page_text_backup', '')
        
        # Extract ownership section
        match = re.search(
            r'ખાતા નંબર\s*\|\s*ક્ષેત્રફળ\s*\|\s*આકાર\s*\|નોંધ નંબરો તથા ખાતેદાર(.*?)(?=Boja and Other|બોજા અને બીજા હક્ક ની વિગતો\s+બોજા|$)',
            raw, re.DOTALL
        )
        
        if not match:
            return '<table class="ownership-table"><tr><td>No data</td></tr></table>'
        
        content = match.group(1).strip()
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        # Parse the data
        entry_numbers = []
        khata_area_tax = ''
        owners = []
        found_separator = False
        
        for line in lines:
            if '---' in line:
                found_separator = True
                continue
            
            if not found_separator:
                # Entry numbers line
                if re.match(r'^[૦-૯0-9,\s]+$', line):
                    entry_numbers.append(line)
            else:
                # After separator - khata line or owner lines
                if '|' in line:
                    # Khata | Area | Tax line with first owner
                    parts = line.split('|')
                    if len(parts) >= 3:
                        khata = parts[0].strip()
                        area = parts[1].strip()
                        rest = parts[2].strip()
                        # Extract tax and first owner
                        tax_match = re.match(r'([૦-૯0-9\.]+)(.*)', rest)
                        if tax_match:
                            tax = tax_match.group(1)
                            first_owner = tax_match.group(2).strip()
                            khata_area_tax = f"{khata} | {area} | {tax}"
                            if first_owner:
                                owners.append(first_owner)
                else:
                    # Owner line
                    if line and not line.startswith('બોજા'):
                        owners.append(line)
        
        # Build HTML
        entry_nums_html = '<br>'.join(entry_numbers) if entry_numbers else ''
        
        owners_html = ''
        for owner in owners:
            # Make owner names clickable like in portal
            owners_html += f'<div class="owner-line"><a href="#">{owner}</a></div>'
        
        return f"""
        <table class="ownership-table">
            <tr>
                <th>ખાતા નંબર | ક્ષેત્રફળ | આકાર |</th>
                <th>નોંધ નંબરો તથા ખાતેદાર</th>
            </tr>
            <tr>
                <td>
                    <div class="entry-numbers">{entry_nums_html}</div>
                    <div class="separator-line"></div>
                    <div>{khata_area_tax}</div>
                </td>
                <td>
                    {owners_html}
                </td>
            </tr>
        </table>
        """
    
    def _build_boja_table(self, data: dict) -> str:
        """Build boja table with proper format"""
        raw = data.get('raw_page_text_backup', '')
        
        # Extract boja section
        match = re.search(
            r'બોજા અને બીજા હક્ક ની વિગતો\s+બોજા અને બીજા હક્ક ની વિગતો(.*?)(?=\*\s*અહીં|Content Owned|$)',
            raw, re.DOTALL
        )
        
        if not match:
            # Try alternate pattern
            match = re.search(
                r'બોજા અને બીજા હક્ક ની વિગતો\s*\n(.*?)(?=\*\s*અહીં|Content Owned|$)',
                raw, re.DOTALL
            )
        
        if not match:
            return '<table class="boja-table"><tr><th>બોજા અને બીજા હક્ક ની વિગતો</th></tr><tr><td>-</td></tr></table>'
        
        content = match.group(1).strip()
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        # Parse
        entry_numbers = []
        boja_entries = []
        found_separator = False
        
        for line in lines:
            if '---' in line:
                found_separator = True
                continue
            
            if not found_separator:
                if re.match(r'^[૦-૯0-9,\s]+$', line):
                    entry_numbers.append(line)
            else:
                if line and not line.startswith('બોજા'):
                    boja_entries.append(line)
        
        # Build HTML
        entry_nums_html = '<br>'.join(entry_numbers) if entry_numbers else ''
        
        boja_html = ''
        for entry in boja_entries:
            boja_html += f'<div class="boja-entry">{entry}</div>'
        
        if not boja_html:
            boja_html = '-'
        
        return f"""
        <table class="boja-table">
            <tr>
                <th>બોજા અને બીજા હક્ક ની વિગતો</th>
            </tr>
            <tr>
                <td>
                    <div class="entry-numbers">{entry_nums_html}</div>
                    <div class="separator-line"></div>
                    {boja_html}
                </td>
            </tr>
        </table>
        """
    
    def generate_from_file(self, json_path: str) -> str:
        """Generate HTML from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.generate_html(data)
    
    def save_report(self, json_path: str, output_path: str = None) -> str:
        """Generate and save HTML report"""
        html = self.generate_from_file(json_path)
        
        if not output_path:
            output_path = json_path.replace('.json', '.html')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path


def main():
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        files = sorted(glob.glob("vf7_structured_*.json"))
        if not files:
            print("Usage: python vf7_report.py <structured_json_file>")
            sys.exit(1)
        json_path = files[-1]
    
    print(f"Generating report from: {json_path}")
    generator = VF7ReportGenerator()
    output = generator.save_report(json_path)
    print(f"✓ Report saved: {output}")


if __name__ == "__main__":
    main()
