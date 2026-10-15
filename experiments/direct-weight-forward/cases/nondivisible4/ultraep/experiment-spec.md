# nondivisible4/ultraep

Custom stateful WRITE/Transaction case in experiment-plan.md. Single-switch topology, explicit required-pair TP setup, detailed native/event trace.

Planner input:
```json
{
  "schema_version": 1,
  "npus": 4,
  "experts": 4,
  "top_k": 1,
  "main_placement": [
    0,
    1,
    2,
    3
  ],
  "slots": [
    1,
    1,
    1,
    1
  ],
  "mapping": [
    {
      "source": 0,
      "experts": [
        0
      ]
    },
    {
      "source": 1,
      "experts": [
        0
      ]
    },
    {
      "source": 2,
      "experts": [
        0
      ]
    },
    {
      "source": 3,
      "experts": [
        0
      ]
    },
    {
      "source": 0,
      "experts": [
        0
      ]
    },
    {
      "source": 1,
      "experts": [
        0
      ]
    },
    {
      "source": 2,
      "experts": [
        0
      ]
    },
    {
      "source": 3,
      "experts": [
        0
      ]
    },
    {
      "source": 0,
      "experts": [
        0
      ]
    },
    {
      "source": 1,
      "experts": [
        0
      ]
    },
    {
      "source": 2,
      "experts": [
        0
      ]
    },
    {
      "source": 3,
      "experts": [
        0
      ]
    },
    {
      "source": 0,
      "experts": [
        0
      ]
    },
    {
      "source": 1,
      "experts": [
        0
      ]
    },
    {
      "source": 2,
      "experts": [
        0
      ]
    },
    {
      "source": 3,
      "experts": [
        0
      ]
    },
    {
      "source": 0,
      "experts": [
        0
      ]
    },
    {
      "source": 1,
      "experts": [
        1
      ]
    },
    {
      "source": 2,
      "experts": [
        1
      ]
    },
    {
      "source": 3,
      "experts": [
        1
      ]
    },
    {
      "source": 0,
      "experts": [
        1
      ]
    },
    {
      "source": 1,
      "experts": [
        1
      ]
    },
    {
      "source": 2,
      "experts": [
        2
      ]
    },
    {
      "source": 3,
      "experts": [
        2
      ]
    },
    {
      "source": 3,
      "experts": [
        3
      ]
    }
  ],
  "beta": "1.01",
  "min_replica_quota": 1024
}
```

Parameters (synthetic assumptions):
```json
{
  "model_dim": 65,
  "ff_dim": 129,
  "dtype_bytes": 2,
  "segment_bytes": 333,
  "peak_gflops": 1000,
  "util_permille": 500,
  "setup_ns": 100,
  "seed": 20261015,
  "link_gbps": 100,
  "link_delay_ns": 20,
  "matrices": 3,
  "planning_ns": 200,
  "reroute_ns": 100,
  "weight_completion_ns": 0,
  "weight_strategy": "direct"
}
```

Artifacts: input.txt, config.json, plan.json, transfers.csv, assignments.csv, events.csv, summary.json, console.txt, native/runlog/.
