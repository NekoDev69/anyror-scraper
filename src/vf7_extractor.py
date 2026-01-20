"""
VF-7 Data Extractor - Parses raw AnyROR VF-7 page data into structured format
Enhanced version with better parsing for dynamic fields
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict, Tuple


class VF7Extractor:
    """Extract and structure VF-7 land record data"""
    
    # Gujarati to English digit mapping
    GUJ_DIGITS = {
        '૦': '0', '૧': '1', '૨': '2', '૩': '3', '૪': '4',
        '૫': '5', '૬': '6', '૭': '7', '૮': '8', '૯': '9',
        'પ': '5'  # Common OCR/font issue where પ appears as 5
    }
    
    def __init__(self):
        self.template = self._get_template()
    
    def _get_template(self) -> dict:
        """Return empty structured template"""
        return {
            "meta": {
                "portal_name": "AnyROR Rural Land Record",
                "module": "SURVEY_NUMBER_SEARCH",
                "page_title": "HOME RURAL LAND RECORD SURVEY NUMBER SEARCH",
                "state": "Gujarat",
                "record_type": "VF-7 / RoR (7-12)",
                "data_status_time_local": "",
                "scrape_timestamp_utc": "",
                "language": "gu",
                "disclaimer_local": "અહીં દર્શાવેલ જમીનની વિગતો ફક્ત આપની જાણ માટે જ છે જેને સત્તાવાર નકલ તરીકે ગણવામાં આવશે નહી.",
                "disclaimer_english": "The information provided online is updated and is not an official copy."
            },
            "search_input": {
                "district": "",
                "taluka": "",
                "village": "",
                "survey_or_block_number": "",
                "sub_division_number": "",
                "fetch_mode": "survey_search"
            },
            "location": {
                "district": {"name_en": "", "name_local": ""},
                "taluka": {"name_en": "", "name_local": ""},
                "village": {"name_en": "", "name_local": ""}
            },
            "property_identity": {
                "khata_number": "",
                "survey_number": "",
                "block_number": "",
                "sub_division_number": "",
                "old_survey_number": "",
                "old_survey_notes": "",
                "upin": "",
                "land_type": "Unknown"
            },
            "owners": [],
            "land_details": {
                "total_area_raw": "",
                "area_hectare": None,
                "area_are": None,
                "area_sqm": None,
                "area_total_sqm": None,
                "area_sq_yd": None,
                "assessment_tax": "",
                "land_revenue": "",
                "tenure": "",
                "tenure_local": "",
                "land_use": "",
                "land_use_local": "",
                "farm_name": "",
                "irrigation_type": "",
                "soil_type": "",
                "crop_details": "",
                "remarks": "",
                "boundaries": {"north": "", "south": "", "east": "", "west": ""}
            },
            "entry_numbers": [],
            "rights_and_remarks": {
                "entry_details": [],
                "notes_raw": ""
            },
            "related_documents": {
                "vf6": {"available": False, "url": ""},
                "vf8a": {"available": False, "url": ""},
                "vf7": {"available": False, "url": ""},
                "mutation_register": {"available": False, "url": ""}
            },
            "raw_page_text_backup": ""
        }
    
    def guj_to_eng(self, text: str) -> str:
        """Convert Gujarati digits to English"""
        if not text:
            return text
        result = text
        for guj, eng in self.GUJ_DIGITS.items():
            result = result.replace(guj, eng)
        return result
    
    def parse_area(self, area_str: str) -> dict:
        """
        Parse area string like '૦-પ૬-૬૬' or '0-56-66' (H-A-M format)
        H = Hectare, A = Are (100 sqm), M = Square meters
        """
        result = {
            "raw": area_str,
            "hectare": None,
            "are": None, 
            "sqm": None,
            "total_sqm": None,
            "sq_yd": None
        }
        if not area_str:
            return result
        
        # Convert to English digits
        area_eng = self.guj_to_eng(area_str)
        
        # Try to parse H-A-M format
        match = re.match(r'(\d+)-(\d+)-(\d+)', area_eng)
        if match:
            hectare = int(match.group(1))
            are = int(match.group(2))
            sqm = int(match.group(3))
            total_sqm = (hectare * 10000) + (are * 100) + sqm
            
            result["hectare"] = hectare
            result["are"] = are
            result["sqm"] = sqm
            result["total_sqm"] = total_sqm
            result["sq_yd"] = round(total_sqm * 1.19599, 2)
        
        return result
    
    def extract_entry_numbers_header(self, text: str) -> List[str]:
        """
        Extract entry numbers from header line like '૭,૧૮૬,પ૮૩,૬૩૨,૬પ૧,૮૯પ,'
        These appear before the dashed line
        """
        entries = []
        if not text:
            return entries
        
        # Find the line before the dashed separator
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Skip header and separator lines
            if 'ખાતા નંબર' in line or '---' in line or not line:
                continue
            
            # Check if this is an entry numbers line (comma-separated numbers)
            # Convert to English first
            line_eng = self.guj_to_eng(line)
            
            # Match comma-separated numbers
            if re.match(r'^[\d,\s]+,?\s*$', line_eng):
                # Extract all numbers
                nums = re.findall(r'\d+', line_eng)
                entries.extend(nums)
                break  # Only first such line
        
        return entries
    
    def parse_khata_area_line(self, text: str) -> Tuple[str, str, str]:
        """
        Parse the main data line like '૩૨ | ૦-પ૬-૬૬ | ૭.૦૦ભગતભાઈ...'
        Returns: (khata_number, area_raw, assessment_tax)
        """
        khata = ""
        area = ""
        assessment = ""
        
        if not text:
            return khata, area, assessment
        
        # Find line with pipe separators after the dashed line
        lines = text.split('\n')
        found_separator = False
        
        for line in lines:
            line = line.strip()
            
            if '---' in line:
                found_separator = True
                continue
            
            if found_separator and '|' in line:
                # This is the data line: "૩૨ | ૦-પ૬-૬૬ | ૭.૦૦NameHere"
                parts = line.split('|')
                if len(parts) >= 3:
                    khata = self.guj_to_eng(parts[0].strip())
                    area = parts[1].strip()  # Keep original for raw
                    
                    # Third part has assessment + first owner name
                    third = parts[2].strip()
                    # Extract decimal number at start (assessment)
                    assess_match = re.match(r'([૦-૯0-9]+\.[૦-૯0-9]+)', third)
                    if assess_match:
                        assessment = self.guj_to_eng(assess_match.group(1))
                
                break
        
        return khata, area, assessment
    
    def parse_owners_table1(self, text: str) -> List[dict]:
        """
        Extract ALL owners from table 1 text
        Handles two formats:
        1. "OwnerName(EntryNo)" - with entry number
        2. "OwnerName" - without entry number (standalone lines)
        """
        owners = []
        if not text:
            return owners
        
        lines = text.split('\n')
        found_separator = False
        first_data_line = True
        
        for line in lines:
            line = line.strip()
            
            if '---' in line:
                found_separator = True
                continue
            
            if not found_separator or not line:
                continue
            
            # Skip if it's just entry numbers (comma-separated)
            line_eng = self.guj_to_eng(line)
            if re.match(r'^[\d,\s|]+$', line_eng):
                continue
            
            # Try to find owners with (entry_number) pattern first
            # Note: પ (Gujarati 'pa') is often used as 5 in entry numbers
            pattern = r'([^()\n]+)\(([૦-૯પ0-9]+)\)'
            matches = re.findall(pattern, line)
            
            if matches:
                # Process owners with entry numbers
                for name_part, entry_no in matches:
                    name_part = name_part.strip()
                    entry_no_eng = self.guj_to_eng(entry_no)
                    
                    # Clean up name - remove leading pipe/number data from first entry
                    if first_data_line and '|' in name_part:
                        parts = name_part.split('|')
                        if len(parts) >= 3:
                            last_part = parts[-1].strip()
                            name_match = re.sub(r'^[૦-૯પ0-9]+\.[૦-૯પ0-9]+', '', last_part).strip()
                            name_part = name_match
                        first_data_line = False
                    
                    if not name_part or len(name_part) < 2:
                        continue
                    
                    owner = self._parse_owner_details(name_part, entry_no_eng)
                    if owner:
                        owners.append(owner)
            else:
                # No entry number pattern - check if this is a standalone owner name
                # First data line has khata|area|assessment format
                if first_data_line and '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        # Extract name from after assessment value
                        last_part = parts[-1].strip()
                        # Remove leading decimal number (assessment)
                        name_match = re.sub(r'^[૦-૯પ0-9]+\.[૦-૯પ0-9]+', '', last_part).strip()
                        if name_match and len(name_match) > 2:
                            owner = self._parse_owner_details(name_match, "")
                            if owner:
                                owners.append(owner)
                    first_data_line = False
                else:
                    # Standalone owner name line (no entry number, no pipe)
                    # Skip lines that look like headers or numbers
                    if not re.match(r'^[૦-૯પ0-9,\s\-|]+$', line) and len(line) > 2:
                        owner = self._parse_owner_details(line, "")
                        if owner:
                            owners.append(owner)
        
        return owners
    
    def _parse_owner_details(self, name_part: str, entry_no: str) -> Optional[dict]:
        """Parse owner name and extract relationship info"""
        if not name_part or len(name_part) < 2:
            return None
        
        father_husband = ""
        ownership_type = "ખાતેદાર"
        
        if "સ.વા." in name_part or "સ.વા" in name_part:
            # Minor with guardian: "રાજદિપ રમેશભાઈ સ.વા. વર્ષાબા રમેશભાઈ ગોહિલ"
            ownership_type = "સગીર વતી"
            parts = re.split(r'સ\.?વા\.?\s*', name_part)
            if len(parts) == 2:
                name_part = parts[0].strip()
                father_husband = f"Guardian: {parts[1].strip()}"
        
        elif "ના પત્ની" in name_part or "ની વિધવા" in name_part:
            # Wife/widow
            if "ની વિધવા" in name_part:
                ownership_type = "વિધવા"
                parts = name_part.split("ની વિધવા")
            else:
                ownership_type = "પત્ની"
                parts = name_part.split("ના પત્ની")
            
            if len(parts) >= 1:
                pre = parts[0].strip()
                if " તે " in pre:
                    name_husband = pre.split(" તે ")
                    name_part = name_husband[0].strip()
                    father_husband = name_husband[1].strip() if len(name_husband) > 1 else ""
                else:
                    name_part = pre
        
        return {
            "owner_name": name_part,
            "owner_father_or_husband_name": father_husband,
            "ownership_type": ownership_type,
            "share": "",
            "entry_number": entry_no,
            "owner_address_or_remark": ""
        }
    
    def parse_encumbrances_table2(self, text: str) -> Tuple[List[str], List[dict]]:
        """
        Parse encumbrance/rights table (બોજા અને બીજા હક્ક ની વિગતો)
        Returns: (entry_numbers, encumbrance_details)
        """
        entry_numbers = []
        encumbrances = []
        
        if not text:
            return entry_numbers, encumbrances
        
        lines = text.split('\n')
        found_separator = False
        
        for line in lines:
            line = line.strip()
            
            # Skip header
            if 'બોજા અને બીજા હક્ક' in line:
                continue
            
            # Entry numbers line (before separator)
            if not found_separator and not '---' in line:
                line_eng = self.guj_to_eng(line)
                if re.match(r'^[\d,\s]+,?\s*$', line_eng):
                    nums = re.findall(r'\d+', line_eng)
                    entry_numbers.extend(nums)
                continue
            
            if '---' in line:
                found_separator = True
                continue
            
            if not found_separator or not line:
                continue
            
            # Parse encumbrance entries with <entry_no> pattern
            # Example: "બેંક ઓફ ઈન્ડિયા સાતેમ શાખાનો રુ.પ૦૦૦ના તારણમાં બો<૧૦૪૮>"
            # Note: પ (Gujarati 'pa') is often used as 5 in entry numbers
            pattern = r'(.+?)<([૦-૯પ0-9]+)>'
            matches = re.findall(pattern, line)
            
            for desc, entry_no in matches:
                desc = desc.strip()
                entry_no_eng = self.guj_to_eng(entry_no)
                
                # Determine type based on keywords
                enc_type = "અન્ય"  # Other
                if "બેંક" in desc or "તારણ" in desc or "બોજો" in desc or "બો" in desc:
                    enc_type = "બેંક બોજો"  # Bank encumbrance
                elif "નહેર" in desc or "કમાન્ડ" in desc:
                    enc_type = "સિંચાઈ"  # Irrigation
                elif "હુકમ" in desc or "મામલતદાર" in desc:
                    enc_type = "સરકારી હુકમ"  # Government order
                elif "એકસપ્રેસ" in desc or "જમીન" in desc and "નીમ" in desc:
                    enc_type = "સંપાદન"  # Acquisition
                
                # Extract amount if present
                amount = ""
                amt_match = re.search(r'રુ\.?\s*([૦-૯0-9,]+)', desc)
                if amt_match:
                    amount = self.guj_to_eng(amt_match.group(1))
                
                encumbrances.append({
                    "entry_no": entry_no_eng,
                    "entry_date": "",
                    "type": enc_type,
                    "description": desc,
                    "amount": amount,
                    "status": "Active",
                    "office": "",
                    "order_reference": ""
                })
        
        return entry_numbers, encumbrances
    
    def extract(self, raw_data: dict, search_params: dict = None) -> dict:
        """
        Main extraction method - converts raw scrape data to structured format
        """
        result = self._get_template()
        
        # Set timestamp
        result["meta"]["scrape_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        
        # Set search inputs if provided
        if search_params:
            if search_params.get("district"):
                result["search_input"]["district"] = search_params["district"].get("value", "")
                result["location"]["district"]["name_local"] = search_params["district"].get("text", "")
            
            if search_params.get("taluka"):
                result["search_input"]["taluka"] = search_params["taluka"].get("value", "")
                result["location"]["taluka"]["name_local"] = search_params["taluka"].get("text", "")
            
            if search_params.get("village"):
                result["search_input"]["village"] = search_params["village"].get("value", "")
                village_text = search_params["village"].get("text", "")
                # Clean village name (remove code suffix like "- 086")
                village_clean = re.sub(r'\s*-\s*\d+$', '', village_text)
                result["location"]["village"]["name_local"] = village_clean
            
            if search_params.get("survey"):
                result["search_input"]["survey_or_block_number"] = search_params["survey"].get("value", "")
                result["property_identity"]["survey_number"] = search_params["survey"].get("text", "")
        
        # Extract property details from new fields
        prop_details = raw_data.get("property_details", {})
        
        # Data status time
        if prop_details.get("data_status_time"):
            result["meta"]["data_status_time_local"] = prop_details["data_status_time"]
        
        # UPIN
        if prop_details.get("upin"):
            result["property_identity"]["upin"] = prop_details["upin"]
        
        # Old survey number and notes
        if prop_details.get("old_survey_number"):
            result["property_identity"]["old_survey_number"] = prop_details["old_survey_number"]
        if prop_details.get("old_survey_notes"):
            result["property_identity"]["old_survey_notes"] = prop_details["old_survey_notes"]
        
        # Tenure (સત્તાપ્રકાર)
        if prop_details.get("tenure"):
            tenure_val = prop_details["tenure"]
            result["land_details"]["tenure_local"] = tenure_val
            # Map to English
            if "જુની શરત" in tenure_val or "જુ.શ" in tenure_val:
                result["land_details"]["tenure"] = "Old Tenure"
            elif "નવી શરત" in tenure_val or "ન.શ" in tenure_val:
                result["land_details"]["tenure"] = "New Tenure"
            elif "ખાલસા" in tenure_val:
                result["land_details"]["tenure"] = "Khalsa"
            else:
                result["land_details"]["tenure"] = tenure_val
        
        # Land use (જમીનનો ઉપયોગ)
        if prop_details.get("land_use"):
            land_use_val = prop_details["land_use"]
            result["land_details"]["land_use_local"] = land_use_val
            # Map to English
            if "ખેતીલાયક" in land_use_val or "ખેતી" in land_use_val:
                result["land_details"]["land_use"] = "Agricultural"
            elif "પો.ખ" in land_use_val or "પોત ખરાબ" in land_use_val:
                result["land_details"]["land_use"] = "Barren/Wasteland"
            elif "બિનખેતી" in land_use_val or "NA" in land_use_val.upper():
                result["land_details"]["land_use"] = "Non-Agricultural"
            elif "ગૌચર" in land_use_val:
                result["land_details"]["land_use"] = "Grazing Land"
            else:
                result["land_details"]["land_use"] = land_use_val
        
        # Farm name (ખેતરનું નામ)
        if prop_details.get("farm_name"):
            result["land_details"]["farm_name"] = prop_details["farm_name"]
        
        # Remarks
        if prop_details.get("remarks"):
            result["land_details"]["remarks"] = prop_details["remarks"]
        
        # Override area/assessment from property_details if available
        if prop_details.get("total_area"):
            result["land_details"]["total_area_raw"] = prop_details["total_area"]
            area_parsed = self.parse_area(prop_details["total_area"])
            result["land_details"]["area_hectare"] = area_parsed["hectare"]
            result["land_details"]["area_are"] = area_parsed["are"]
            result["land_details"]["area_sqm"] = area_parsed["sqm"]
            result["land_details"]["area_total_sqm"] = area_parsed["total_sqm"]
            result["land_details"]["area_sq_yd"] = area_parsed["sq_yd"]
        
        if prop_details.get("assessment_tax"):
            result["land_details"]["assessment_tax"] = self.guj_to_eng(prop_details["assessment_tax"])
        
        # Process tables
        tables = raw_data.get("tables", [])
        
        # Store raw backup
        all_text = "\n\n".join([t.get("text", "") for t in tables])
        full_page = raw_data.get("full_page_text", "")
        result["raw_page_text_backup"] = full_page if full_page else all_text
        
        # Parse first table (khata, area, owners)
        if len(tables) > 0:
            table1_text = tables[0].get("text", "")
            
            # Extract entry numbers from header
            header_entries = self.extract_entry_numbers_header(table1_text)
            result["entry_numbers"].extend(header_entries)
            
            # Extract khata, area, assessment (only if not already set from property_details)
            khata, area_raw, assessment = self.parse_khata_area_line(table1_text)
            result["property_identity"]["khata_number"] = khata
            
            if not result["land_details"]["total_area_raw"]:
                result["land_details"]["total_area_raw"] = area_raw
                area_parsed = self.parse_area(area_raw)
                result["land_details"]["area_hectare"] = area_parsed["hectare"]
                result["land_details"]["area_are"] = area_parsed["are"]
                result["land_details"]["area_sqm"] = area_parsed["sqm"]
                result["land_details"]["area_total_sqm"] = area_parsed["total_sqm"]
                result["land_details"]["area_sq_yd"] = area_parsed["sq_yd"]
            
            if not result["land_details"]["assessment_tax"]:
                result["land_details"]["assessment_tax"] = assessment
            
            # Extract owners
            result["owners"] = self.parse_owners_table1(table1_text)
        
        # Parse second table (encumbrances/rights)
        if len(tables) > 1:
            table2_text = tables[1].get("text", "")
            result["rights_and_remarks"]["notes_raw"] = table2_text
            
            enc_entries, encumbrances = self.parse_encumbrances_table2(table2_text)
            result["entry_numbers"].extend(enc_entries)
            result["rights_and_remarks"]["entry_details"] = encumbrances
        
        # Deduplicate entry numbers
        result["entry_numbers"] = list(dict.fromkeys(result["entry_numbers"]))
        
        # Determine land type based on content
        if result["land_details"]["land_use"] == "Non-Agricultural":
            result["property_identity"]["land_type"] = "NA"
        elif "બીનખેતી" in all_text or "NA" in all_text.upper():
            result["property_identity"]["land_type"] = "NA"
        elif result["land_details"]["land_use"] == "Agricultural" or "ખેતી" in all_text:
            result["property_identity"]["land_type"] = "Agriculture"
        
        # Count stats
        result["meta"]["owner_count"] = len(result["owners"])
        result["meta"]["encumbrance_count"] = len(result["rights_and_remarks"]["entry_details"])
        
        return result
    
    def extract_from_scrape_result(self, scrape_result: dict) -> dict:
        """
        Convenience method to extract from full scrape result
        """
        search_params = {
            "district": scrape_result.get("district"),
            "taluka": scrape_result.get("taluka"),
            "village": scrape_result.get("village"),
            "survey": scrape_result.get("survey")
        }
        
        raw_data = scrape_result.get("data", {})
        
        return self.extract(raw_data, search_params)

    def extract_owner_list(self, raw_data: dict) -> List[dict]:
        """
        Extract results from owner search matches table
        """
        results = []
        tables = raw_data.get("tables", [])
        
        # Look for the table that contains owner search results
        # Usually it's the only table visible after a search
        for table in tables:
            text = table.get("text", "")
            if "ખાતેદારનું નામ" in text or "ખાતા નંબર" in text:
                # Parse the text-based table
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or "ક્રમ" in line or "---" in line:
                        continue
                    
                    # Try to match: SrNo | KhataNo | SurveyNo | OwnerName
                    # Since we get raw text from Playwright .text_content(), 
                    # it might have various separators or just spaces.
                    # Based on browser analysis, the content is in cells.
                    
                    # Split by common separators or multiple spaces
                    parts = [p.strip() for p in re.split(r'\s{2,}|\|', line) if p.strip()]
                    if len(parts) >= 4:
                        results.append({
                            "sr_no": self.guj_to_eng(parts[0]),
                            "khata_no": self.guj_to_eng(parts[1]),
                            "survey_no": self.guj_to_eng(parts[2]),
                            "owner_name": parts[3]
                        })
                break
                
        return results


# Standalone usage and testing
if __name__ == "__main__":
    import json
    import sys
    import glob
    
    if len(sys.argv) > 1:
        # Process specific file
        filepath = sys.argv[1]
        with open(filepath, 'r', encoding='utf-8') as f:
            scrape_result = json.load(f)
        
        extractor = VF7Extractor()
        structured = extractor.extract_from_scrape_result(scrape_result)
        
        print(json.dumps(structured, ensure_ascii=False, indent=2))
    else:
        # Process all raw files in current directory
        raw_files = glob.glob("vf7_raw_*.json")
        
        if not raw_files:
            print("Usage: python vf7_extractor.py [result_file.json]")
            print("Or place vf7_raw_*.json files in current directory")
            sys.exit(1)
        
        extractor = VF7Extractor()
        
        for filepath in raw_files:
            print(f"\n{'='*60}")
            print(f"Processing: {filepath}")
            print('='*60)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                scrape_result = json.load(f)
            
            structured = extractor.extract_from_scrape_result(scrape_result)
            
            # Save structured output
            out_file = filepath.replace("_raw_", "_structured_v2_")
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(structured, f, ensure_ascii=False, indent=2)
            
            # Print summary
            print(f"Village: {structured['location']['village']['name_local']}")
            print(f"Khata: {structured['property_identity']['khata_number']}")
            print(f"Survey: {structured['property_identity']['survey_number']}")
            print(f"Area: {structured['land_details']['total_area_raw']} ({structured['land_details']['area_total_sqm']} sqm)")
            print(f"Owners: {len(structured['owners'])}")
            print(f"Encumbrances: {len(structured['rights_and_remarks']['entry_details'])}")
            print(f"Saved: {out_file}")
