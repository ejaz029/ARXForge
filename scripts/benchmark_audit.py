import argparse

from engine.benchmark import benchmark_to_json


def main():
    parser = argparse.ArgumentParser(description="Benchmark ARXForge audit performance.")
    parser.add_argument("--mode", default="all", choices=["small", "medium", "large", "all"])
    parser.add_argument("--runs", default=3, type=int)
    parser.add_argument("--xsd", default=None)
    args = parser.parse_args()
    print(benchmark_to_json(mode=args.mode, runs=args.runs, xsd_path=args.xsd))


if __name__ == "__main__":
    main()

