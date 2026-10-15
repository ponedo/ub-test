# fixed64/two-stage

Same accepted single-switch network and compute. See experiment-plan.md.

```json
{
  "planner_input": {
    "schema_version": 1,
    "npus": 64,
    "experts": 128,
    "top_k": 2,
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
      7,
      8,
      8,
      9,
      9,
      10,
      10,
      11,
      11,
      12,
      12,
      13,
      13,
      14,
      14,
      15,
      15,
      16,
      16,
      17,
      17,
      18,
      18,
      19,
      19,
      20,
      20,
      21,
      21,
      22,
      22,
      23,
      23,
      24,
      24,
      25,
      25,
      26,
      26,
      27,
      27,
      28,
      28,
      29,
      29,
      30,
      30,
      31,
      31,
      32,
      32,
      33,
      33,
      34,
      34,
      35,
      35,
      36,
      36,
      37,
      37,
      38,
      38,
      39,
      39,
      40,
      40,
      41,
      41,
      42,
      42,
      43,
      43,
      44,
      44,
      45,
      45,
      46,
      46,
      47,
      47,
      48,
      48,
      49,
      49,
      50,
      50,
      51,
      51,
      52,
      52,
      53,
      53,
      54,
      54,
      55,
      55,
      56,
      56,
      57,
      57,
      58,
      58,
      59,
      59,
      60,
      60,
      61,
      61,
      62,
      62,
      63,
      63
    ],
    "slots": [
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1,
      1
    ],
    "mapping": [
      {
        "source": 0,
        "experts": [
          0,
          1
        ]
      },
      {
        "source": 1,
        "experts": [
          0,
          2
        ]
      },
      {
        "source": 2,
        "experts": [
          0,
          3
        ]
      },
      {
        "source": 3,
        "experts": [
          0,
          4
        ]
      },
      {
        "source": 4,
        "experts": [
          0,
          5
        ]
      },
      {
        "source": 5,
        "experts": [
          0,
          6
        ]
      },
      {
        "source": 6,
        "experts": [
          0,
          7
        ]
      },
      {
        "source": 7,
        "experts": [
          0,
          8
        ]
      },
      {
        "source": 8,
        "experts": [
          0,
          9
        ]
      },
      {
        "source": 9,
        "experts": [
          0,
          10
        ]
      },
      {
        "source": 10,
        "experts": [
          0,
          11
        ]
      },
      {
        "source": 11,
        "experts": [
          0,
          12
        ]
      },
      {
        "source": 12,
        "experts": [
          0,
          13
        ]
      },
      {
        "source": 13,
        "experts": [
          0,
          14
        ]
      },
      {
        "source": 14,
        "experts": [
          0,
          15
        ]
      },
      {
        "source": 15,
        "experts": [
          0,
          16
        ]
      },
      {
        "source": 16,
        "experts": [
          0,
          17
        ]
      },
      {
        "source": 17,
        "experts": [
          0,
          18
        ]
      },
      {
        "source": 18,
        "experts": [
          0,
          19
        ]
      },
      {
        "source": 19,
        "experts": [
          0,
          20
        ]
      },
      {
        "source": 20,
        "experts": [
          0,
          21
        ]
      },
      {
        "source": 21,
        "experts": [
          0,
          22
        ]
      },
      {
        "source": 22,
        "experts": [
          0,
          23
        ]
      },
      {
        "source": 23,
        "experts": [
          0,
          24
        ]
      },
      {
        "source": 24,
        "experts": [
          0,
          25
        ]
      },
      {
        "source": 25,
        "experts": [
          0,
          26
        ]
      },
      {
        "source": 26,
        "experts": [
          0,
          27
        ]
      },
      {
        "source": 27,
        "experts": [
          0,
          28
        ]
      },
      {
        "source": 28,
        "experts": [
          0,
          29
        ]
      },
      {
        "source": 29,
        "experts": [
          0,
          30
        ]
      },
      {
        "source": 30,
        "experts": [
          0,
          31
        ]
      },
      {
        "source": 31,
        "experts": [
          0,
          32
        ]
      },
      {
        "source": 32,
        "experts": [
          0,
          33
        ]
      },
      {
        "source": 33,
        "experts": [
          0,
          34
        ]
      },
      {
        "source": 34,
        "experts": [
          0,
          35
        ]
      },
      {
        "source": 35,
        "experts": [
          0,
          36
        ]
      },
      {
        "source": 36,
        "experts": [
          0,
          37
        ]
      },
      {
        "source": 37,
        "experts": [
          0,
          38
        ]
      },
      {
        "source": 38,
        "experts": [
          0,
          39
        ]
      },
      {
        "source": 39,
        "experts": [
          0,
          40
        ]
      },
      {
        "source": 40,
        "experts": [
          0,
          41
        ]
      },
      {
        "source": 41,
        "experts": [
          0,
          42
        ]
      },
      {
        "source": 42,
        "experts": [
          0,
          43
        ]
      },
      {
        "source": 43,
        "experts": [
          0,
          44
        ]
      },
      {
        "source": 44,
        "experts": [
          0,
          45
        ]
      },
      {
        "source": 45,
        "experts": [
          0,
          46
        ]
      },
      {
        "source": 46,
        "experts": [
          0,
          47
        ]
      },
      {
        "source": 47,
        "experts": [
          0,
          48
        ]
      },
      {
        "source": 48,
        "experts": [
          0,
          49
        ]
      },
      {
        "source": 49,
        "experts": [
          0,
          50
        ]
      },
      {
        "source": 50,
        "experts": [
          0,
          51
        ]
      },
      {
        "source": 51,
        "experts": [
          0,
          52
        ]
      },
      {
        "source": 52,
        "experts": [
          0,
          53
        ]
      },
      {
        "source": 53,
        "experts": [
          0,
          54
        ]
      },
      {
        "source": 54,
        "experts": [
          0,
          55
        ]
      },
      {
        "source": 55,
        "experts": [
          0,
          56
        ]
      },
      {
        "source": 56,
        "experts": [
          0,
          57
        ]
      },
      {
        "source": 57,
        "experts": [
          0,
          58
        ]
      },
      {
        "source": 58,
        "experts": [
          0,
          59
        ]
      },
      {
        "source": 59,
        "experts": [
          0,
          60
        ]
      },
      {
        "source": 60,
        "experts": [
          0,
          61
        ]
      },
      {
        "source": 61,
        "experts": [
          0,
          62
        ]
      },
      {
        "source": 62,
        "experts": [
          0,
          63
        ]
      },
      {
        "source": 63,
        "experts": [
          0,
          64
        ]
      },
      {
        "source": 0,
        "experts": [
          0,
          65
        ]
      },
      {
        "source": 1,
        "experts": [
          0,
          66
        ]
      },
      {
        "source": 2,
        "experts": [
          0,
          67
        ]
      },
      {
        "source": 3,
        "experts": [
          0,
          68
        ]
      },
      {
        "source": 4,
        "experts": [
          0,
          69
        ]
      },
      {
        "source": 5,
        "experts": [
          0,
          70
        ]
      },
      {
        "source": 6,
        "experts": [
          0,
          71
        ]
      },
      {
        "source": 7,
        "experts": [
          0,
          72
        ]
      },
      {
        "source": 8,
        "experts": [
          0,
          73
        ]
      },
      {
        "source": 9,
        "experts": [
          0,
          74
        ]
      },
      {
        "source": 10,
        "experts": [
          0,
          75
        ]
      },
      {
        "source": 11,
        "experts": [
          0,
          76
        ]
      },
      {
        "source": 12,
        "experts": [
          0,
          77
        ]
      },
      {
        "source": 13,
        "experts": [
          0,
          78
        ]
      },
      {
        "source": 14,
        "experts": [
          0,
          79
        ]
      },
      {
        "source": 15,
        "experts": [
          0,
          80
        ]
      },
      {
        "source": 16,
        "experts": [
          0,
          81
        ]
      },
      {
        "source": 17,
        "experts": [
          0,
          82
        ]
      },
      {
        "source": 18,
        "experts": [
          0,
          83
        ]
      },
      {
        "source": 19,
        "experts": [
          0,
          84
        ]
      },
      {
        "source": 20,
        "experts": [
          0,
          85
        ]
      },
      {
        "source": 21,
        "experts": [
          0,
          86
        ]
      },
      {
        "source": 22,
        "experts": [
          0,
          87
        ]
      },
      {
        "source": 23,
        "experts": [
          0,
          88
        ]
      },
      {
        "source": 24,
        "experts": [
          0,
          89
        ]
      },
      {
        "source": 25,
        "experts": [
          0,
          90
        ]
      },
      {
        "source": 26,
        "experts": [
          0,
          91
        ]
      },
      {
        "source": 27,
        "experts": [
          0,
          92
        ]
      },
      {
        "source": 28,
        "experts": [
          0,
          93
        ]
      },
      {
        "source": 29,
        "experts": [
          0,
          94
        ]
      },
      {
        "source": 30,
        "experts": [
          0,
          95
        ]
      },
      {
        "source": 31,
        "experts": [
          0,
          96
        ]
      },
      {
        "source": 32,
        "experts": [
          0,
          97
        ]
      },
      {
        "source": 33,
        "experts": [
          0,
          98
        ]
      },
      {
        "source": 34,
        "experts": [
          0,
          99
        ]
      },
      {
        "source": 35,
        "experts": [
          0,
          100
        ]
      },
      {
        "source": 36,
        "experts": [
          0,
          101
        ]
      },
      {
        "source": 37,
        "experts": [
          0,
          102
        ]
      },
      {
        "source": 38,
        "experts": [
          0,
          103
        ]
      },
      {
        "source": 39,
        "experts": [
          0,
          104
        ]
      },
      {
        "source": 40,
        "experts": [
          0,
          105
        ]
      },
      {
        "source": 41,
        "experts": [
          0,
          106
        ]
      },
      {
        "source": 42,
        "experts": [
          0,
          107
        ]
      },
      {
        "source": 43,
        "experts": [
          0,
          108
        ]
      },
      {
        "source": 44,
        "experts": [
          0,
          109
        ]
      },
      {
        "source": 45,
        "experts": [
          0,
          110
        ]
      },
      {
        "source": 46,
        "experts": [
          0,
          111
        ]
      },
      {
        "source": 47,
        "experts": [
          0,
          112
        ]
      },
      {
        "source": 48,
        "experts": [
          0,
          113
        ]
      },
      {
        "source": 49,
        "experts": [
          0,
          114
        ]
      },
      {
        "source": 50,
        "experts": [
          0,
          115
        ]
      },
      {
        "source": 51,
        "experts": [
          0,
          116
        ]
      },
      {
        "source": 52,
        "experts": [
          0,
          117
        ]
      },
      {
        "source": 53,
        "experts": [
          0,
          118
        ]
      },
      {
        "source": 54,
        "experts": [
          0,
          119
        ]
      },
      {
        "source": 55,
        "experts": [
          0,
          120
        ]
      },
      {
        "source": 56,
        "experts": [
          0,
          121
        ]
      },
      {
        "source": 57,
        "experts": [
          0,
          122
        ]
      },
      {
        "source": 58,
        "experts": [
          0,
          123
        ]
      },
      {
        "source": 59,
        "experts": [
          0,
          124
        ]
      },
      {
        "source": 60,
        "experts": [
          0,
          125
        ]
      },
      {
        "source": 61,
        "experts": [
          0,
          126
        ]
      },
      {
        "source": 62,
        "experts": [
          0,
          127
        ]
      },
      {
        "source": 63,
        "experts": [
          0,
          1
        ]
      }
    ],
    "beta": "1.01",
    "min_replica_quota": 1024,
    "mode": "upstream-compatible",
    "allow_zero_main": false,
    "rounding": "code",
    "oracle_epsilon": "0.01",
    "kernel_stage": 1,
    "locality_aware": true
  },
  "model_overrides": {},
  "relay_overrides": {}
}
```
