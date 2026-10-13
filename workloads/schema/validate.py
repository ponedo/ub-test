"""python3 -m workloads.schema.validate TRACE.csv"""
import argparse
import json
from .trace import read_trace, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace')
    args = parser.parse_args()
    try:
        print(json.dumps(validate(read_trace(args.trace)), sort_keys=True))
    except (ValueError, OSError) as e:
        parser.error(str(e))


if __name__ == '__main__':
    main()
