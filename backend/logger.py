"""Logging and reporting module."""

import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from utils import format_cost


def configure_logging(level: str = "INFO", log_file: str = "simulation.log") -> None:
    """
    Configure structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


class JSONLogger:
    """JSON-structured logger for machine parsing."""
    
    def __init__(self, log_file: str = "simulation.jsonl"):
        """
        Initialize JSON logger.
        
        Args:
            log_file: Path to JSON log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = open(self.log_file, "a")
    
    def log_round(
        self,
        round_num: int,
        decisions: Dict,
        costs: Dict,
        penalties: List[Dict],
        inventory_snapshot: Dict,
    ) -> None:
        """
        Log round data in JSON format.
        
        Args:
            round_num: Round number
            decisions: Decision data
            costs: Cost breakdown
            penalties: List of penalties
            inventory_snapshot: Current inventory state
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "round": round_num,
            "decisions": decisions,
            "costs": costs,
            "penalties": penalties,
            "inventory": inventory_snapshot,
        }
        
        json.dump(log_entry, self.file_handle)
        self.file_handle.write("\n")
        self.file_handle.flush()
    
    def close(self) -> None:
        """Close log file."""
        self.file_handle.close()


def generate_final_report(log_data: List[Dict], output_path: str) -> None:
    """
    Generate final report from log data.
    
    Args:
        log_data: List of log entries
        output_path: Path to output file
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate totals
    total_cost = sum(entry.get("costs", {}).get("total_cost", 0.0) for entry in log_data)
    total_penalties = sum(entry.get("costs", {}).get("penalties", 0.0) for entry in log_data)
    total_operational = total_cost - total_penalties
    
    # Count penalties by type
    penalty_counts = {}
    for entry in log_data:
        for penalty in entry.get("penalties", []):
            code = penalty.get("code", "UNKNOWN")
            penalty_counts[code] = penalty_counts.get(code, 0) + 1
    
    # Generate report
    report = {
        "summary": {
            "total_rounds": len(log_data),
            "total_cost": total_cost,
            "total_operational_cost": total_operational,
            "total_penalties": total_penalties,
            "penalty_breakdown": penalty_counts,
        },
        "rounds": log_data,
    }
    
    # Write JSON report
    json_path = output_file.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Write text summary
    text_path = output_file.with_suffix(".txt")
    with open(text_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("SIMULATION FINAL REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Rounds: {len(log_data)}\n")
        f.write(f"Total Cost: {format_cost(total_cost)}\n")
        f.write(f"Operational Cost: {format_cost(total_operational)}\n")
        f.write(f"Penalties: {format_cost(total_penalties)}\n\n")
        f.write("Penalty Breakdown:\n")
        for code, count in penalty_counts.items():
            f.write(f"  {code}: {count}\n")
        f.write("\n" + "=" * 80 + "\n")
    
    logging.info(f"Final report generated: {json_path} and {text_path}")

