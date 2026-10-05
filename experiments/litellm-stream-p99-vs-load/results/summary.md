# Results

2026-10-05T03:55:02+00:00 · Windows 11 AMD64 · Intel64 Family 6 Model 183 Stepping 1, GenuineIntel (24 logical CPUs) · litellm 1.103.0 (workers=2) · node v22.17.0
3 trial(s) × 20 s per condition, closed loop, streaming. Values are the median across trials; p99 range is min to max across trials.

| scenario | c | target | ok (all trials) | req/s | p50 ms | p99 ms | p99 range | gw cores | loadgen cores | mock cores |
|---|--:|---|--:|--:|--:|--:|---|--:|--:|--:|
| zero-latency upstream | 1 | direct | 119653 | 1929.82 | 0.42 | 1.15 | 0.91 to 1.3 |  | 0.58 | 0.47 |
| zero-latency upstream | 1 | litellm | 1167 | 19.5 | 45.64 | 83.4 | 78.3 to 92.6 | 0.9 | 0.07 | 0.02 |
| zero-latency upstream | 2 | direct | 216454 | 3581.44 | 0.4 | 2.65 | 1.76 to 2.86 |  | 0.79 | 0.69 |
| zero-latency upstream | 2 | litellm | 1661 | 16.91 | 114.68 | 187.61 | 55.97 to 197.66 | 0.89 | 0.07 | 0.01 |
| zero-latency upstream | 4 | direct | 232520 | 3696.25 | 0.77 | 4.43 | 3.82 to 5.66 |  | 0.8 | 0.69 |
| zero-latency upstream | 4 | litellm | 2900 | 46.99 | 87.22 | 191.74 | 154.82 to 201.04 | 1.84 | 0.11 | 0.01 |
| zero-latency upstream | 10 | direct | 267951 | 3993.9 | 1.95 | 6.73 | 3.65 to 11.08 |  | 0.83 | 0.76 |
| zero-latency upstream | 10 | litellm | 3029 | 48.82 | 265.13 | 417.43 | 245.9 to 432.34 | 1.84 | 0.1 | 0.02 |
| model-like upstream (~ | 10 | direct | 519 | 8.21 | 1178.25 | 1251.48 | 1236.62 to 1265.87 |  | 0.04 | 0.03 |
| model-like upstream (~ | 10 | litellm | 512 | 8.07 | 1222.39 | 1322.04 | 1317.78 to 1391.69 | 0.5 | 0.04 | 0.05 |
| model-like upstream (~ | 50 | direct | 2550 | 40.54 | 1218.53 | 1266.11 | 1265 to 1272.37 |  | 0.1 | 0.08 |
| model-like upstream (~ | 50 | litellm | 1861 | 32.67 | 1452.97 | 2161.49 | 1885.2 to 2720.5 | 1.13 | 0.08 | 0.05 |
| model-like upstream (~ | 100 | direct | 5100 | 80.5 | 1233.42 | 1297.38 | 1284.1 to 1300.82 |  | 0.15 | 0.19 |
| model-like upstream (~ | 100 | litellm | 2946 | 43.38 | 2548.76 | 3376.24 | 2481.36 to 3925.36 | 1.37 | 0.09 | 0.07 |

## Added latency (litellm minus direct, medians across trials)

| scenario | c | added p50 ms | added p99 ms | direct p50 ms |
|---|--:|--:|--:|--:|
| zero-latency upstream | 1 | 45.2 | 82.2 | 0.42 |
| zero-latency upstream | 2 | 114.3 | 185.0 | 0.4 |
| zero-latency upstream | 4 | 86.5 | 187.3 | 0.77 |
| zero-latency upstream | 10 | 263.2 | 410.7 | 1.95 |
| model-like upstream (~ | 10 | 44.1 | 70.6 | 1178.25 |
| model-like upstream (~ | 50 | 234.4 | 895.4 | 1218.53 |
| model-like upstream (~ | 100 | 1315.3 | 2078.9 | 1233.42 |
