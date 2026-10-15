# uniform4/no-balancing

Custom stateful WRITE/Transaction case in experiment-plan.md. Single-switch topology, explicit required-pair TP setup, detailed native/event trace.

Planner input:
```json
{
  "schema_version": 1,
  "npus": 4,
  "experts": 8,
  "top_k": 1,
  "main_placement": [
    0,
    0,
    1,
    1,
    2,
    2,
    3,
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
      "source": 0,
      "experts": [
        2
      ]
    },
    {
      "source": 1,
      "experts": [
        2
      ]
    },
    {
      "source": 3,
      "experts": [
        3
      ]
    },
    {
      "source": 0,
      "experts": [
        3
      ]
    },
    {
      "source": 1,
      "experts": [
        3
      ]
    },
    {
      "source": 2,
      "experts": [
        3
      ]
    },
    {
      "source": 0,
      "experts": [
        4
      ]
    },
    {
      "source": 1,
      "experts": [
        4
      ]
    },
    {
      "source": 2,
      "experts": [
        4
      ]
    },
    {
      "source": 3,
      "experts": [
        4
      ]
    },
    {
      "source": 1,
      "experts": [
        5
      ]
    },
    {
      "source": 2,
      "experts": [
        5
      ]
    },
    {
      "source": 3,
      "experts": [
        5
      ]
    },
    {
      "source": 0,
      "experts": [
        5
      ]
    },
    {
      "source": 2,
      "experts": [
        6
      ]
    },
    {
      "source": 3,
      "experts": [
        6
      ]
    },
    {
      "source": 0,
      "experts": [
        6
      ]
    },
    {
      "source": 1,
      "experts": [
        6
      ]
    },
    {
      "source": 3,
      "experts": [
        7
      ]
    },
    {
      "source": 0,
      "experts": [
        7
      ]
    },
    {
      "source": 1,
      "experts": [
        7
      ]
    },
    {
      "source": 2,
      "experts": [
        7
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
  "model_dim": 64,
  "ff_dim": 128,
  "dtype_bytes": 2,
  "segment_bytes": 1024,
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
