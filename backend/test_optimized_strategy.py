#!/usr/bin/env python3
"""
Quick test script for the optimized greedy strategy.
"""

import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from config import API_KEY, BASE_URL
from simulation_runner import SimulationRunner
from logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def test_strategy():
    """Test the optimized greedy strategy."""
    logger.info("=" * 80)
    logger.info("TESTING OPTIMIZED SAFE GREEDY STRATEGY")
    logger.info("=" * 80)
    
    # Create runner
    runner = SimulationRunner(base_url=BASE_URL)
    
    logger.info(f"API Base URL: {BASE_URL}")
    logger.info(f"API Key: {API_KEY[:8]}...")
    
    # Test configuration
    logger.info("\n📋 Strategy Configuration:")
    logger.info(f"   Buffer: {runner.decision_maker.config.PASSENGER_BUFFER_PERCENT * 100}% + "
                f"{runner.decision_maker.config.MIN_BUFFER_KITS} kits minimum")
    logger.info(f"   HUB reorder: < {runner.decision_maker.config.HUB_REORDER_THRESHOLD * 100}% capacity")
    logger.info(f"   HUB target: {runner.decision_maker.config.HUB_TARGET_LEVEL * 100}% capacity")
    
    # Run simulation
    try:
        logger.info("\n🚀 Starting simulation...")
        logger.info("   This will run ALL 720 rounds (30 days)")
        logger.info("   Press Ctrl+C to stop early\n")
        
        result = runner.run(
            api_key=API_KEY,
            max_rounds=720,
            stop_existing=True
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ SIMULATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Rounds completed: {result['rounds_completed']}")
        logger.info(f"Total cost: ${result['total_cost']:,.2f}")
        logger.info(f"Session ID: {result['session_id']}")
        
        # Analyze penalties
        cost_log = result.get('cost_log', [])
        if cost_log:
            total_penalties = sum(
                entry.get('costs', {}).get('penalties', 0) 
                for entry in cost_log
            )
            logger.info(f"Total penalties: ${total_penalties:,.2f}")
            
            if total_penalties == 0:
                logger.info("🎉 ZERO PENALTIES! Perfect execution!")
            elif total_penalties < 1000:
                logger.info("✅ Low penalties - very good!")
            else:
                logger.warning(f"⚠️  High penalties - check logs for issues")
        
        return result
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Simulation interrupted by user")
        return None
    except Exception as e:
        logger.error(f"\n❌ Simulation failed: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    test_strategy()
