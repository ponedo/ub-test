# chunk_lt_ta/chunk-streaming

Same accepted single-switch network and compute. See experiment-plan.md.

```json
{
  "planner_input": {
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
      }
    ],
    "beta": "1.01",
    "min_replica_quota": 1024
  },
  "model_overrides": {},
  "relay_overrides": {
    "force_relay": true,
    "chunk_bytes": 512
  }
}
```
