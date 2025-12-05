#!/usr/bin/env python3
"""
Data validator for OpenAQ measurements.

Validates measurement records for schema compliance, data quality,
and reasonable value ranges. Generates quality metrics and reports.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import yaml


class DataValidator:
    """Validates OpenAQ measurement data quality and schema compliance."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize validator with configuration."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.validation_rules = self.config.get("validation", {})
        self.parameter_ranges = self.validation_rules.get("parameter_ranges", {})
        self.required_fields = self.validation_rules.get("required_fields", [])
        
        self.metrics = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "warnings": 0,
            "errors": []
        }

    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Could not load config file: {e}")
            return {}

    def validate_record_schema(self, record: Dict) -> Tuple[bool, List[str]]:
        """
        Validate that a record has all required fields.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        for field in self.required_fields:
            if field not in record:
                errors.append(f"Missing required field: {field}")
        
        # Check nested structure
        if "parameter" in record:
            param = record["parameter"]
            if not isinstance(param, dict):
                errors.append("'parameter' must be a dictionary")
            elif "id" not in param or "name" not in param:
                errors.append("'parameter' must have 'id' and 'name' fields")
        
        if "period" in record:
            period = record["period"]
            if not isinstance(period, dict):
                errors.append("'period' must be a dictionary")
            elif "datetimeFrom" not in period:
                errors.append("'period' must have 'datetimeFrom' field")
        
        return len(errors) == 0, errors

    def validate_value_range(self, record: Dict) -> Tuple[bool, List[str]]:
        """
        Validate that measurement values are within reasonable ranges.
        
        Returns:
            (is_valid, warning_messages)
        """
        warnings = []
        
        value = record.get("value")
        if value is None:
            return True, []  # Already caught by schema validation
        
        parameter_name = record.get("parameter", {}).get("name")
        if not parameter_name:
            return True, []
        
        # Check if we have validation rules for this parameter
        if parameter_name not in self.parameter_ranges:
            return True, []  # No rules defined, assume valid
        
        min_val, max_val = self.parameter_ranges[parameter_name]
        
        if not isinstance(value, (int, float)):
            warnings.append(f"Value is not numeric: {value}")
            return False, warnings
        
        if value < min_val or value > max_val:
            warnings.append(
                f"{parameter_name} value {value} outside valid range [{min_val}, {max_val}]"
            )
            return False, warnings
        
        return True, warnings

    def validate_timestamp(self, record: Dict) -> Tuple[bool, List[str]]:
        """
        Validate timestamp format and reasonableness.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        period = record.get("period", {})
        datetime_from = period.get("datetimeFrom", {}).get("utc")
        
        if not datetime_from:
            return True, []  # Already caught by schema validation
        
        # Validate ISO format
        try:
            dt = datetime.fromisoformat(datetime_from.replace("Z", "+00:00"))
            
            # Check if timestamp is reasonable (not in future, not too old)
            now = datetime.utcnow()
            if dt > now:
                errors.append(f"Timestamp is in the future: {datetime_from}")
            
            # Check if timestamp is not older than 5 years
            age_days = (now - dt).days
            if age_days > 5 * 365:
                errors.append(f"Timestamp is older than 5 years: {datetime_from}")
            
        except (ValueError, AttributeError) as e:
            errors.append(f"Invalid timestamp format: {datetime_from} ({e})")
        
        return len(errors) == 0, errors

    def validate_record(self, record: Dict, record_index: int = 0) -> Dict[str, Any]:
        """
        Validate a single measurement record.
        
        Returns:
            Validation result dictionary
        """
        result = {
            "index": record_index,
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Schema validation
        schema_valid, schema_errors = self.validate_record_schema(record)
        if not schema_valid:
            result["valid"] = False
            result["errors"].extend(schema_errors)
        
        # Value range validation
        range_valid, range_warnings = self.validate_value_range(record)
        if not range_valid:
            result["warnings"].extend(range_warnings)
        
        # Timestamp validation
        timestamp_valid, timestamp_errors = self.validate_timestamp(record)
        if not timestamp_valid:
            result["valid"] = False
            result["errors"].extend(timestamp_errors)
        
        return result

    def validate_dataset(self, records: List[Dict], sample_size: Optional[int] = None) -> Dict:
        """
        Validate a dataset of measurement records.
        
        Args:
            records: List of measurement records
            sample_size: If provided, only validate a random sample
        
        Returns:
            Validation report dictionary
        """
        self.metrics = {
            "total_records": len(records),
            "valid_records": 0,
            "invalid_records": 0,
            "warnings": 0,
            "validation_errors": [],
            "sample_validation_results": []
        }
        
        if not records:
            return self.metrics
        
        # If sample_size is specified, validate only a sample
        if sample_size and sample_size < len(records):
            import random
            records_to_validate = random.sample(records, sample_size)
            self.metrics["sampled"] = True
            self.metrics["sample_size"] = sample_size
        else:
            records_to_validate = records
            self.metrics["sampled"] = False
        
        # Validate each record
        for i, record in enumerate(records_to_validate):
            validation_result = self.validate_record(record, i)
            
            if validation_result["valid"]:
                self.metrics["valid_records"] += 1
            else:
                self.metrics["invalid_records"] += 1
                # Store first 10 errors for reporting
                if len(self.metrics["validation_errors"]) < 10:
                    self.metrics["validation_errors"].append({
                        "index": i,
                        "errors": validation_result["errors"]
                    })
            
            if validation_result["warnings"]:
                self.metrics["warnings"] += len(validation_result["warnings"])
            
            # Store sample results (first 5)
            if len(self.metrics["sample_validation_results"]) < 5:
                self.metrics["sample_validation_results"].append(validation_result)
        
        # Calculate quality score
        if self.metrics["total_records"] > 0:
            self.metrics["quality_score"] = (
                self.metrics["valid_records"] / self.metrics["total_records"]
            ) * 100
        else:
            self.metrics["quality_score"] = 0.0
        
        return self.metrics

    def generate_report(self, metrics: Optional[Dict] = None) -> str:
        """Generate a human-readable validation report."""
        if metrics is None:
            metrics = self.metrics
        
        report = []
        report.append("=" * 60)
        report.append("DATA VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        report.append("")
        report.append(f"Total Records: {metrics.get('total_records', 0)}")
        report.append(f"Valid Records: {metrics.get('valid_records', 0)}")
        report.append(f"Invalid Records: {metrics.get('invalid_records', 0)}")
        report.append(f"Warnings: {metrics.get('warnings', 0)}")
        report.append(f"Quality Score: {metrics.get('quality_score', 0):.2f}%")
        report.append("")
        
        if metrics.get("sampled"):
            report.append(f"Note: Validated sample of {metrics.get('sample_size')} records")
            report.append("")
        
        # Show validation errors
        validation_errors = metrics.get("validation_errors", [])
        if validation_errors:
            report.append("VALIDATION ERRORS:")
            report.append("-" * 60)
            for error in validation_errors[:10]:
                report.append(f"Record {error['index']}:")
                for err_msg in error["errors"]:
                    report.append(f"  - {err_msg}")
            
            if len(validation_errors) > 10:
                report.append(f"... and {len(validation_errors) - 10} more errors")
            report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)

    def validate_file(self, file_path: Path) -> Dict:
        """
        Validate a location JSON file.
        
        Returns:
            Validation metrics dictionary
        """
        print(f"Validating file: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return {
                    "error": "File does not contain a list of records",
                    "valid": False
                }
            
            metrics = self.validate_dataset(data)
            metrics["file_path"] = str(file_path)
            
            return metrics
            
        except (json.JSONDecodeError, IOError) as e:
            return {
                "file_path": str(file_path),
                "error": f"Failed to load file: {e}",
                "valid": False
            }


def main():
    """Command-line interface for data validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate OpenAQ measurement data")
    parser.add_argument(
        "--file", "-f",
        type=str,
        required=True,
        help="Path to location JSON file to validate"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.yaml file (default: ./config.yaml)"
    )
    parser.add_argument(
        "--sample", "-s",
        type=int,
        default=None,
        help="Validate only a random sample of N records"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save validation report to file"
    )
    
    args = parser.parse_args()
    
    # Initialize validator
    config_path = Path(args.config) if args.config else None
    validator = DataValidator(config_path=config_path)
    
    # Validate file
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        exit(1)
    
    # Load and validate data
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print("Error: File does not contain a list of records")
            exit(1)
        
        metrics = validator.validate_dataset(data, sample_size=args.sample)
        report = validator.generate_report(metrics)
        
        # Output report
        print(report)
        
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
                f.write("\n\nDetailed Metrics:\n")
                f.write(json.dumps(metrics, indent=2))
            print(f"\nReport saved to: {output_path}")
        
        # Exit with error code if quality is poor
        if metrics.get("quality_score", 0) < 90:
            print("\nWarning: Data quality below 90%")
            exit(1)
        else:
            exit(0)
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
