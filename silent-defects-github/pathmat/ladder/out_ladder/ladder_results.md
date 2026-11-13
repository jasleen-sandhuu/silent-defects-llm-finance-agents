# Ladder results

Groups = cases linked by a shared company. A defect is a violated process rule, not proven harm. Tokens/cost are in the JSON; price per token is an assumption.

| tier | condition | stratum | runs | complete | accuracy | mean calls | failed calls | silent/correct | sigma [95% group CI] | case-level upper | group-level upper |
|---|---|---|---|---|---|---|---|---|---|---|---|
| short | baseline | all | 120 | 120 | 93.3% | 3.0 | 0.0% | 0/112 | 0.0% [0.0%, 0.0%] | 5.2% | 20.6% |
| short | baseline | A | 60 | 60 | 90.0% | 3.0 | 0.0% | 0/54 | 0.0% [0.0%, 0.0%] | 10.5% | 20.9% |
| short | flaky | all | 120 | 119 | 93.3% | 4.5 | 20.2% | 0/111 | 0.0% [0.0%, 0.0%] | 5.3% | 20.8% |
| short | flaky | A | 60 | 60 | 93.3% | 4.2 | 17.9% | 0/56 | 0.0% [0.0%, 0.0%] | 10.2% | 20.2% |
| short | combined | all | 120 | 120 | 89.2% | 4.5 | 19.3% | 0/107 | 0.0% [0.0%, 0.0%] | 5.5% | 21.5% |
| short | combined | A | 60 | 60 | 86.7% | 4.2 | 15.9% | 0/52 | 0.0% [0.0%, 0.0%] | 10.9% | 21.6% |
| medium | baseline | all | 120 | 120 | 91.7% | 11.3 | 0.4% | 0/110 | 0.0% [0.0%, 0.0%] | 5.3% | 20.9% |
| medium | baseline | A | 60 | 60 | 93.3% | 11.1 | 0.2% | 0/56 | 0.0% [0.0%, 0.0%] | 10.2% | 20.1% |
| medium | flaky | all | 120 | 120 | 75.0% | 18.1 | 21.3% | 0/90 | 0.0% [0.0%, 0.0%] | 6.5% | 19.2% |
| medium | flaky | A | 60 | 60 | 71.7% | 17.8 | 21.5% | 0/43 | 0.0% [0.0%, 0.0%] | 13.2% | 26.0% |
| medium | combined | all | 120 | 120 | 79.2% | 16.7 | 21.2% | 0/95 | 0.0% [0.0%, 0.0%] | 6.1% | 21.2% |
| medium | combined | A | 60 | 60 | 80.0% | 16.6 | 20.9% | 0/48 | 0.0% [0.0%, 0.0%] | 11.9% | 29.3% |
| long | baseline | all | 120 | 120 | 94.2% | 18.6 | 0.1% | 0/113 | 0.0% [0.0%, 0.0%] | 5.2% | 30.0% |
| long | baseline | A | 60 | 60 | 100.0% | 18.7 | 0.1% | 0/60 | 0.0% [0.0%, 0.0%] | 9.5% | 44.9% |
| long | flaky | all | 120 | 120 | 54.2% | 30.1 | 23.4% | 14/65 | 21.5% [12.0%, 31.9%] | 54.9% | 100.0% |
| long | flaky | A | 60 | 60 | 58.3% | 30.9 | 23.1% | 7/35 | 20.0% [7.1%, 34.4%] | 59.6% | 100.0% |
| long | combined | all | 120 | 120 | 42.5% | 28.9 | 24.5% | 5/51 | 9.8% [2.6%, 18.2%] | 38.5% | 90.0% |
| long | combined | A | 60 | 60 | 43.3% | 28.9 | 25.2% | 2/26 | 7.7% [0.0%, 16.0%] | 43.7% | 78.0% |

## H1: sigma(long) minus sigma(short), company bootstrap, one-sided, Holm-adjusted

| condition | difference | 95% interval | p (Holm) |
|---|---|---|---|
| baseline | +0.0 pp | [+0.0, +0.0] | 1.000 |
| flaky | +21.5 pp | [+11.5, +32.1] | 0.000 |
| combined | +9.8 pp | [+2.8, +18.2] | 0.009 |
