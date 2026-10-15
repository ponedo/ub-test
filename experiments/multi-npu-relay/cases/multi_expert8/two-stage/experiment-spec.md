# multi_expert8/two-stage

Same accepted single-switch network and compute. See experiment-plan.md.

```json
{
  "planner_input": {
    "schema_version": 1,
    "npus": 8,
    "experts": 16,
    "top_k": 1,
    "main_placement": [
      0,
      0,
      1,
      1,
      2,
      2,
      3,
      3,
      4,
      4,
      5,
      5,
      6,
      6,
      7,
      7
    ],
    "slots": [
      3,
      3,
      3,
      3,
      3,
      3,
      3,
      3
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
        "source": 4,
        "experts": [
          0
        ]
      },
      {
        "source": 5,
        "experts": [
          0
        ]
      },
      {
        "source": 6,
        "experts": [
          0
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          0
        ]
      },
      {
        "source": 5,
        "experts": [
          0
        ]
      },
      {
        "source": 6,
        "experts": [
          0
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          0
        ]
      },
      {
        "source": 5,
        "experts": [
          0
        ]
      },
      {
        "source": 6,
        "experts": [
          0
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          0
        ]
      },
      {
        "source": 5,
        "experts": [
          0
        ]
      },
      {
        "source": 6,
        "experts": [
          0
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          0
        ]
      },
      {
        "source": 5,
        "experts": [
          0
        ]
      },
      {
        "source": 6,
        "experts": [
          0
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          1
        ]
      },
      {
        "source": 5,
        "experts": [
          1
        ]
      },
      {
        "source": 6,
        "experts": [
          1
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          1
        ]
      },
      {
        "source": 5,
        "experts": [
          1
        ]
      },
      {
        "source": 6,
        "experts": [
          1
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          1
        ]
      },
      {
        "source": 5,
        "experts": [
          1
        ]
      },
      {
        "source": 6,
        "experts": [
          1
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          1
        ]
      },
      {
        "source": 5,
        "experts": [
          1
        ]
      },
      {
        "source": 6,
        "experts": [
          1
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          1
        ]
      },
      {
        "source": 5,
        "experts": [
          1
        ]
      },
      {
        "source": 6,
        "experts": [
          1
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          2
        ]
      },
      {
        "source": 5,
        "experts": [
          2
        ]
      },
      {
        "source": 6,
        "experts": [
          2
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          2
        ]
      },
      {
        "source": 5,
        "experts": [
          2
        ]
      },
      {
        "source": 6,
        "experts": [
          2
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          2
        ]
      },
      {
        "source": 5,
        "experts": [
          2
        ]
      },
      {
        "source": 6,
        "experts": [
          2
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          2
        ]
      },
      {
        "source": 5,
        "experts": [
          2
        ]
      },
      {
        "source": 6,
        "experts": [
          2
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          2
        ]
      },
      {
        "source": 5,
        "experts": [
          2
        ]
      },
      {
        "source": 6,
        "experts": [
          2
        ]
      },
      {
        "source": 7,
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
        "source": 4,
        "experts": [
          3
        ]
      },
      {
        "source": 5,
        "experts": [
          3
        ]
      },
      {
        "source": 6,
        "experts": [
          3
        ]
      },
      {
        "source": 7,
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
        "source": 3,
        "experts": [
          3
        ]
      },
      {
        "source": 4,
        "experts": [
          3
        ]
      },
      {
        "source": 5,
        "experts": [
          3
        ]
      },
      {
        "source": 6,
        "experts": [
          3
        ]
      },
      {
        "source": 7,
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
        "source": 3,
        "experts": [
          3
        ]
      },
      {
        "source": 4,
        "experts": [
          3
        ]
      },
      {
        "source": 5,
        "experts": [
          3
        ]
      },
      {
        "source": 6,
        "experts": [
          3
        ]
      },
      {
        "source": 7,
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
        "source": 3,
        "experts": [
          3
        ]
      },
      {
        "source": 4,
        "experts": [
          3
        ]
      },
      {
        "source": 5,
        "experts": [
          3
        ]
      },
      {
        "source": 6,
        "experts": [
          3
        ]
      },
      {
        "source": 7,
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
        "source": 3,
        "experts": [
          3
        ]
      },
      {
        "source": 4,
        "experts": [
          3
        ]
      },
      {
        "source": 5,
        "experts": [
          3
        ]
      },
      {
        "source": 6,
        "experts": [
          3
        ]
      },
      {
        "source": 7,
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
      }
    ],
    "beta": "1.01",
    "min_replica_quota": 1024
  },
  "model_overrides": {},
  "relay_overrides": {
    "force_relay": true
  }
}
```
