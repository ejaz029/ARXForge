#!/usr/bin/env python
"""
Test runner script for ARXML Agentic AI system.
Runs tests in phases as specified.
"""
import sys
import subprocess
import os

def run_phase(phase_num, phase_name, test_file):
    """Run a specific test phase."""
    print(f"\n{'='*60}")
    print(f"🧪 Phase {phase_num}: {phase_name}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "-s"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    return result.returncode == 0


def main():
    """Run all test phases."""
    phases = [
        (1, "Unit Testing (Tools Level)", "tests/test_tools.py"),
        (2, "Intent Router Testing", "tests/test_intent_router.py"),
        (3, "Agent Planning Test", "tests/test_planning.py"),
        (4, "Tool Chaining Test", "tests/test_tool_chaining.py"),
        (5, "RAG Fallback Test", "tests/test_rag_fallback.py"),
        (6, "Memory Test", "tests/test_memory.py"),
        (7, "Stress Test", "tests/test_stress.py"),
    ]
    
    results = []
    
    for phase_num, phase_name, test_file in phases:
        success = run_phase(phase_num, phase_name, test_file)
        results.append((phase_num, phase_name, success))
        
        if not success:
            print(f"\n❌ Phase {phase_num} failed. Continue? (y/n): ", end="")
            response = input().strip().lower()
            if response != 'y':
                break
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}\n")
    
    for phase_num, phase_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"Phase {phase_num}: {phase_name} - {status}")
    
    total = len(results)
    passed = sum(1 for _, _, success in results if success)
    
    print(f"\nTotal: {passed}/{total} phases passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} phase(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
