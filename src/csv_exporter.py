"""
CSV Exporter for Gujarat AnyROR Land Records
Fast, reliable CSV export for parallel scraping results
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class VF7CSVExporter:
    """Fast CSV exporter for VF-7 land records"""

    def __init__(self):
        """Initialize CSV exporter"""
        self.supported_formats = ["single_sheet", "detailed", "summary"]

    def export_single_sheet(
        self,
        results: List[Dict],
        output_path: str,
        district_name: str = "",
        taluka_name: str = "",
    ) -> str:
        """
        Export all results to a single CSV sheet (flat format)

        Args:
            results: List of scraping results (structured format)
            output_path: Path to save CSV file
            district_name: District name for metadata
            taluka_name: Taluka name for metadata

        Returns:
            Path to created CSV file
        """
        print(f"[CSV] Exporting {len(results)} results to single sheet: {output_path}")

        # Filter successful results
        successful_results = [r for r in results if r.get("success", False)]
        print(f"[CSV] Successful results: {len(successful_results)}")

        if not successful_results:
            print("[CSV] No successful results to export")
            return output_path

        # Define comprehensive headers
        headers = [
            # Basic Info
            "task_id",
            "village_code",
            "village_name",
            "success",
            "district_name",
            "taluka_name",
            "timestamp",
            # Property Identity
            "survey_number",
            "upin",
            "khata_number",
            "old_survey_number",
            # Land Details
            "total_area_raw",
            "area_hectare",
            "area_are",
            "area_sqm",
            "area_sq_yd",
            "assessment_tax",
            "tenure",
            "tenure_local",
            "land_use",
            "land_use_local",
            "farm_name",
            "remarks",
            # Owner Information
            "owner_count",
            "owner_names",
            "owner_details",
            # Encumbrance Information
            "encumbrance_count",
            "encumbrance_details",
            # Meta Information
            "data_status_time",
            "data_status_time_local",
            # Performance
            "record_count",
            "processing_time",
        ]

        # Write CSV
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for result in successful_results:
                # Extract structured data
                structured = result.get("structured", {})
                location = structured.get("location", {})
                prop_id = structured.get("property_identity", {})
                land = structured.get("land_details", {})
                owners = structured.get("owners", [])
                encumbrances = structured.get("rights_and_remarks", {}).get(
                    "entry_details", []
                )
                meta = structured.get("meta", {})
                raw_data = result.get("raw", {}).get("data", {})

                # Flatten owner information
                owner_names = "; ".join([o.get("owner_name", "") for o in owners])
                owner_details = "; ".join(
                    [
                        f"{o.get('owner_name', '')} ({o.get('ownership_type', '')})"
                        for o in owners
                    ]
                )

                # Flatten encumbrance information
                enc_details = "; ".join(
                    [
                        f"{e.get('type', '')}: {e.get('description', '')[:50]}"
                        for e in encumbrances
                    ]
                )

                # Create row
                row = {
                    "task_id": result.get("task_id", ""),
                    "village_code": result.get("village_code", ""),
                    "village_name": location.get("village", {}).get("name_local", ""),
                    "success": result.get("success", False),
                    "district_name": location.get("district", {}).get("name_local", "")
                    or district_name,
                    "taluka_name": location.get("taluka", {}).get("name_local", "")
                    or taluka_name,
                    "timestamp": result.get("timestamp", ""),
                    # Property Identity
                    "survey_number": prop_id.get("survey_number", ""),
                    "upin": prop_id.get("upin", ""),
                    "khata_number": prop_id.get("khata_number", ""),
                    "old_survey_number": prop_id.get("old_survey_number", ""),
                    # Land Details
                    "total_area_raw": land.get("total_area_raw", ""),
                    "area_hectare": land.get("area_hectare", ""),
                    "area_are": land.get("area_are", ""),
                    "area_sqm": land.get("area_sqm", ""),
                    "area_sq_yd": land.get("area_sq_yd", ""),
                    "assessment_tax": land.get("assessment_tax", ""),
                    "tenure": land.get("tenure", ""),
                    "tenure_local": land.get("tenure_local", ""),
                    "land_use": land.get("land_use", ""),
                    "land_use_local": land.get("land_use_local", ""),
                    "farm_name": land.get("farm_name", ""),
                    "remarks": land.get("remarks", ""),
                    # Owner Information
                    "owner_count": len(owners),
                    "owner_names": owner_names,
                    "owner_details": owner_details,
                    # Encumbrance Information
                    "encumbrance_count": len(encumbrances),
                    "encumbrance_details": enc_details,
                    # Meta Information
                    "data_status_time": meta.get("data_status_time", ""),
                    "data_status_time_local": meta.get("data_status_time_local", ""),
                    # Performance
                    "record_count": raw_data.get("record_count", 0),
                    "processing_time": result.get("processing_time", ""),
                }

                writer.writerow(row)

        print(f"[CSV] ✓ Single sheet exported: {output_path}")
        return output_path

    def export_detailed(
        self,
        results: List[Dict],
        output_dir: str,
        district_name: str = "",
        taluka_name: str = "",
    ) -> Dict[str, str]:
        """
        Export to multiple detailed CSV files

        Args:
            results: List of scraping results
            output_dir: Directory to save CSV files
            district_name: District name for metadata
            taluka_name: Taluka name for metadata

        Returns:
            Dict with file paths
        """
        print(
            f"[CSV] Exporting {len(results)} results to detailed CSVs in: {output_dir}"
        )

        os.makedirs(output_dir, exist_ok=True)

        # Filter successful results
        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            print("[CSV] No successful results to export")
            return {}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files = {}

        # 1. Properties CSV
        properties_file = os.path.join(output_dir, f"properties_{timestamp}.csv")
        files["properties"] = self._export_properties_csv(
            successful_results, properties_file, district_name, taluka_name
        )

        # 2. Owners CSV
        owners_file = os.path.join(output_dir, f"owners_{timestamp}.csv")
        files["owners"] = self._export_owners_csv(
            successful_results, owners_file, district_name, taluka_name
        )

        # 3. Encumbrances CSV
        encumbrances_file = os.path.join(output_dir, f"encumbrances_{timestamp}.csv")
        files["encumbrances"] = self._export_encumbrances_csv(
            successful_results, encumbrances_file, district_name, taluka_name
        )

        # 4. Summary CSV
        summary_file = os.path.join(output_dir, f"summary_{timestamp}.csv")
        files["summary"] = self._export_summary_csv(
            results, summary_file, district_name, taluka_name
        )

        print(f"[CSV] ✓ Detailed export complete: {len(files)} files")
        return files

    def _export_properties_csv(
        self,
        results: List[Dict],
        output_path: str,
        district_name: str,
        taluka_name: str,
    ) -> str:
        """Export properties to CSV"""
        headers = [
            "task_id",
            "village_code",
            "village_name",
            "district_name",
            "taluka_name",
            "survey_number",
            "upin",
            "khata_number",
            "old_survey_number",
            "total_area_raw",
            "area_hectare",
            "area_are",
            "area_sqm",
            "area_sq_yd",
            "assessment_tax",
            "tenure",
            "tenure_local",
            "land_use",
            "land_use_local",
            "farm_name",
            "remarks",
            "owner_count",
            "encumbrance_count",
            "data_status_time_local",
            "timestamp",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for result in results:
                structured = result.get("structured", {})
                location = structured.get("location", {})
                prop_id = structured.get("property_identity", {})
                land = structured.get("land_details", {})
                meta = structured.get("meta", {})

                row = {
                    "task_id": result.get("task_id", ""),
                    "village_code": result.get("village_code", ""),
                    "village_name": location.get("village", {}).get("name_local", ""),
                    "district_name": location.get("district", {}).get("name_local", "")
                    or district_name,
                    "taluka_name": location.get("taluka", {}).get("name_local", "")
                    or taluka_name,
                    "survey_number": prop_id.get("survey_number", ""),
                    "upin": prop_id.get("upin", ""),
                    "khata_number": prop_id.get("khata_number", ""),
                    "old_survey_number": prop_id.get("old_survey_number", ""),
                    "total_area_raw": land.get("total_area_raw", ""),
                    "area_hectare": land.get("area_hectare", ""),
                    "area_are": land.get("area_are", ""),
                    "area_sqm": land.get("area_sqm", ""),
                    "area_sq_yd": land.get("area_sq_yd", ""),
                    "assessment_tax": land.get("assessment_tax", ""),
                    "tenure": land.get("tenure", ""),
                    "tenure_local": land.get("tenure_local", ""),
                    "land_use": land.get("land_use", ""),
                    "land_use_local": land.get("land_use_local", ""),
                    "farm_name": land.get("farm_name", ""),
                    "remarks": land.get("remarks", ""),
                    "owner_count": len(structured.get("owners", [])),
                    "encumbrance_count": len(
                        structured.get("rights_and_remarks", {}).get(
                            "entry_details", []
                        )
                    ),
                    "data_status_time_local": meta.get("data_status_time_local", ""),
                    "timestamp": result.get("timestamp", ""),
                }

                writer.writerow(row)

        return output_path

    def _export_owners_csv(
        self,
        results: List[Dict],
        output_path: str,
        district_name: str,
        taluka_name: str,
    ) -> str:
        """Export owners to CSV"""
        headers = [
            "task_id",
            "village_code",
            "village_name",
            "district_name",
            "taluka_name",
            "survey_number",
            "upin",
            "owner_sequence",
            "owner_name",
            "owner_father_or_husband_name",
            "ownership_type",
            "entry_number",
            "share",
            "owner_address_or_remark",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for result in results:
                structured = result.get("structured", {})
                location = structured.get("location", {})
                prop_id = structured.get("property_identity", {})
                owners = structured.get("owners", [])

                for idx, owner in enumerate(owners, 1):
                    row = {
                        "task_id": result.get("task_id", ""),
                        "village_code": result.get("village_code", ""),
                        "village_name": location.get("village", {}).get(
                            "name_local", ""
                        ),
                        "district_name": location.get("district", {}).get(
                            "name_local", ""
                        )
                        or district_name,
                        "taluka_name": location.get("taluka", {}).get("name_local", "")
                        or taluka_name,
                        "survey_number": prop_id.get("survey_number", ""),
                        "upin": prop_id.get("upin", ""),
                        "owner_sequence": idx,
                        "owner_name": owner.get("owner_name", ""),
                        "owner_father_or_husband_name": owner.get(
                            "owner_father_or_husband_name", ""
                        ),
                        "ownership_type": owner.get("ownership_type", ""),
                        "entry_number": owner.get("entry_number", ""),
                        "share": owner.get("share", ""),
                        "owner_address_or_remark": owner.get(
                            "owner_address_or_remark", ""
                        ),
                    }

                    writer.writerow(row)

        return output_path

    def _export_encumbrances_csv(
        self,
        results: List[Dict],
        output_path: str,
        district_name: str,
        taluka_name: str,
    ) -> str:
        """Export encumbrances to CSV"""
        headers = [
            "task_id",
            "village_code",
            "village_name",
            "district_name",
            "taluka_name",
            "survey_number",
            "upin",
            "entry_sequence",
            "entry_no",
            "entry_date",
            "type",
            "description",
            "amount",
            "status",
            "office",
            "order_reference",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            for result in results:
                structured = result.get("structured", {})
                location = structured.get("location", {})
                prop_id = structured.get("property_identity", {})
                encumbrances = structured.get("rights_and_remarks", {}).get(
                    "entry_details", []
                )

                for idx, enc in enumerate(encumbrances, 1):
                    row = {
                        "task_id": result.get("task_id", ""),
                        "village_code": result.get("village_code", ""),
                        "village_name": location.get("village", {}).get(
                            "name_local", ""
                        ),
                        "district_name": location.get("district", {}).get(
                            "name_local", ""
                        )
                        or district_name,
                        "taluka_name": location.get("taluka", {}).get("name_local", "")
                        or taluka_name,
                        "survey_number": prop_id.get("survey_number", ""),
                        "upin": prop_id.get("upin", ""),
                        "entry_sequence": idx,
                        "entry_no": enc.get("entry_no", ""),
                        "entry_date": enc.get("entry_date", ""),
                        "type": enc.get("type", ""),
                        "description": enc.get("description", ""),
                        "amount": enc.get("amount", ""),
                        "status": enc.get("status", ""),
                        "office": enc.get("office", ""),
                        "order_reference": enc.get("order_reference", ""),
                    }

                    writer.writerow(row)

        return output_path

    def _export_summary_csv(
        self,
        results: List[Dict],
        output_path: str,
        district_name: str,
        taluka_name: str,
    ) -> str:
        """Export summary to CSV"""
        headers = ["metric", "value", "notes"]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            # Calculate statistics
            successful_results = [r for r in results if r.get("success", False)]
            total_owners = sum(
                len(r.get("structured", {}).get("owners", []))
                for r in successful_results
            )
            total_encumbrances = sum(
                len(
                    r.get("structured", {})
                    .get("rights_and_remarks", {})
                    .get("entry_details", [])
                )
                for r in successful_results
            )

            # Summary data
            summary_data = [
                {
                    "metric": "Export Date",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "notes": "",
                },
                {"metric": "District", "value": district_name, "notes": ""},
                {"metric": "Taluka", "value": taluka_name, "notes": ""},
                {"metric": "Total Records", "value": len(results), "notes": ""},
                {"metric": "Successful", "value": len(successful_results), "notes": ""},
                {
                    "metric": "Failed",
                    "value": len(results) - len(successful_results),
                    "notes": "",
                },
                {
                    "metric": "Success Rate",
                    "value": f"{(len(successful_results) / len(results) * 100):.1f}%",
                    "notes": "",
                },
                {"metric": "Total Owners", "value": total_owners, "notes": ""},
                {
                    "metric": "Total Encumbrances",
                    "value": total_encumbrances,
                    "notes": "",
                },
                {
                    "metric": "Avg Owners per Property",
                    "value": f"{(total_owners / len(successful_results)):.2f}"
                    if successful_results
                    else "0",
                    "notes": "",
                },
                {
                    "metric": "Avg Encumbrances per Property",
                    "value": f"{(total_encumbrances / len(successful_results)):.2f}"
                    if successful_results
                    else "0",
                    "notes": "",
                },
            ]

            for row in summary_data:
                writer.writerow(row)

        return output_path

    def export_from_json_files(
        self,
        json_files: List[str],
        output_path: str,
        format_type: str = "single_sheet",
        district_name: str = "",
        taluka_name: str = "",
    ) -> str:
        """
        Export multiple JSON files to CSV

        Args:
            json_files: List of JSON file paths
            output_path: Output CSV path
            format_type: Export format ('single_sheet', 'detailed')
            district_name: District name
            taluka_name: Taluka name

        Returns:
            Path to created CSV file
        """
        print(f"[CSV] Processing {len(json_files)} JSON files...")

        all_results = []

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Handle different JSON formats
                    if "results" in data:
                        results = data["results"]
                    elif isinstance(data, list):
                        results = data
                    else:
                        results = [data]

                    # Extract structured data if needed
                    for result in results:
                        if "structured" in result:
                            all_results.append(result["structured"])
                        else:
                            all_results.append(result)

            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")
                continue

        print(f"[CSV] Loaded {len(all_results)} results from JSON files")

        # Export based on format type
        if format_type == "single_sheet":
            return self.export_single_sheet(
                all_results, output_path, district_name, taluka_name
            )
        elif format_type == "detailed":
            output_dir = os.path.dirname(output_path) or "."
            return self.export_detailed(
                all_results, output_dir, district_name, taluka_name
            )
        else:
            raise ValueError(f"Unsupported format_type: {format_type}")

    def export_from_directory(
        self,
        input_dir: str,
        output_path: str = None,
        format_type: str = "single_sheet",
        district_name: str = "",
        taluka_name: str = "",
    ) -> str:
        """
        Export all JSON files from directory to CSV

        Args:
            input_dir: Directory containing JSON files
            output_path: Output CSV path (auto-generated if None)
            format_type: Export format ('single_sheet', 'detailed')
            district_name: District name
            taluka_name: Taluka name

        Returns:
            Path to created CSV file(s)
        """
        # Find all JSON files
        json_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.endswith(".json") and not file.startswith("global_summary"):
                    json_files.append(os.path.join(root, file))

        if not json_files:
            raise ValueError(f"No JSON files found in {input_dir}")

        logger.info(f"Found {len(json_files)} JSON files")

        # Auto-generate output path
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if format_type == "single_sheet":
                output_path = os.path.join(input_dir, f"vf7_export_{timestamp}.csv")
            else:
                output_path = os.path.join(input_dir, f"vf7_detailed_{timestamp}")

        return self.export_from_json_files(
            json_files, output_path, format_type, district_name, taluka_name
        )


def main():
    """Example usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python csv_exporter.py <input_dir> [output.csv] [format]")
        print("  python csv_exporter.py output/ results.csv single_sheet")
        print("  python csv_exporter.py output/ detailed detailed")
        return

    input_dir = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    format_type = sys.argv[3] if len(sys.argv) > 3 else "single_sheet"

    exporter = VF7CSVExporter()

    try:
        result_path = exporter.export_from_directory(
            input_dir, output_path, format_type
        )
        print(f"\n✅ CSV exported: {result_path}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
