# FLUX Runtime Performance Benchmark Report v2

**Date:** 2026-04-12 06:25:30 UTC  |  **Platform:** Linux x86_64  |  **Python:** 3.12.13
**Micro iterations:** 100,000  |  **Decode count:** 10,000  |  **Runs:** 5 (warmup 3)

## 1. Opcode Microbenchmarks

| Category | Opcode | Format | ops/sec | ns/op |
|----------|--------|--------|---------|-------|
| arithmetic | ADD | E | 1,506,296 | 663.9 |
| arithmetic | SUB | E | 1,513,834 | 660.6 |
| arithmetic | MUL | E | 1,450,215 | 689.6 |
| arithmetic | DIV | E | 1,356,458 | 737.2 |
| arithmetic | MOD | E | 1,329,741 | 752.0 |
| arithmetic | NEG | B | 2,157,859 | 463.4 |
| arithmetic | INC | B | 2,311,853 | 432.6 |
| arithmetic | DEC | B | 2,252,288 | 444.0 |
| memory | LOAD | E | 1,037,097 | 964.2 |
| memory | STORE | E | 943,925 | 1059.4 |
| memory | MOV | E | 1,220,497 | 819.3 |
| memory | PUSH | B | 1,173,720 | 852.0 |
| memory | POP | B | 1,174,813 | 851.2 |
| control_flow | JMP | F | 6,449,917 | 155.0 |
| control_flow | JZ | E | 6,409,596 | 156.0 |
| control_flow | JNZ | E | 6,383,065 | 156.7 |
| control_flow | JAL | F | 6,391,512 | 156.5 |
| control_flow | RET | A | 6,421,868 | 155.7 |
| logic | AND | E | 1,430,649 | 699.0 |
| logic | OR | E | 1,415,434 | 706.5 |
| logic | XOR | E | 1,399,411 | 714.6 |
| logic | NOT | B | 2,159,954 | 463.0 |
| logic | SHL | E | 1,351,870 | 739.7 |
| logic | SHR | E | 1,355,304 | 737.8 |

### Category Averages

| Category | Avg ops/sec | Avg ns/op |
|----------|-------------|-----------|
| arithmetic | 1,734,818 | 576.4 |
| memory | 1,110,010 | 900.9 |
| control_flow | 6,411,192 | 156.0 |
| logic | 1,518,770 | 658.4 |

## 2. Format Decode Throughput

| Format | Bytes | ops/sec | ns/decode | Exec overhead (ns) |
|--------|-------|---------|-----------|-------------------|
| A | 10,001 | 14,664,554 | 68.2 | -67.9 |
| B | 20,001 | 13,393,676 | 74.7 | -74.0 |
| C | 20,001 | 12,595,010 | 79.4 | 218.6 |
| D | 30,001 | 11,811,546 | 84.7 | 524.1 |
| E | 40,001 | 11,260,320 | 88.8 | 746.8 |
| F | 40,001 | 10,560,474 | 94.7 | -94.3 |
| G | 50,001 | 10,125,903 | 98.8 | 825.8 |

## 3. Macro Benchmarks

| Benchmark | Description | Time (ms) | Cycles |
|-----------|-------------|-----------|--------|
| fibonacci_30 | Fibonacci(30) iterative | 0.15 | 214 |
| bubble_sort_100 | Bubble sort 100 elements (400 compare-swap iters) | 2.36 | 2,844 |
| matmul_5x5 | 5x5 matrix multiply (500 MAC ops) | 1.31 | 2,006 |
| string_process | String scan + compare (1000 iters) | 6.57 | 8,005 |

## 4. Memory Benchmarks

### Allocation Patterns

| Pattern | ops/sec | Peak memory |
|---------|---------|-------------|
| sequential_store | 984,890 | 0 B |
| random_store | 983,568 | 0 B |
| fragmented_store | 957,232 | 66.3 KB |

### Stack Depth

| Max depth | Push/Pop ops | ops/sec |
|-----------|-------------|---------|
| 100 | 200 | 2,131,419 |
| 1000 | 2000 | 2,304,722 |
| 5000 | 10000 | 2,342,243 |
| 10000 | 20000 | 2,303,490 |

### Register Access

| Type | ops/sec |
|------|---------|
| read_triple_reg | 1,225,136 |
| write_inc | 2,320,571 |

## 5. Bottleneck Analysis

### Top 5 Slowest Opcodes

| Rank | Opcode | Category | ns/op | Slowness Ratio |
|------|--------|----------|-------|----------------|
| 1 | STORE | memory | 1059.4 | 1.54x |
| 2 | LOAD | memory | 964.2 | 1.4x |
| 3 | PUSH | memory | 852.0 | 1.24x |
| 4 | POP | memory | 851.2 | 1.23x |
| 5 | MOV | memory | 819.3 | 1.19x |

### Optimization Recommendations

- CRITICAL: memory ops are 5.8x slower than control_flow ops -- prioritize optimization of memory opcode handlers.
- MEDIAN: 689.6 ns/op across all opcodes; top bottleneck 'STORE' is 1.5x median.
- GENERAL: Consider computed-goto dispatch instead of if-elif chains for opcode decoding.
- GENERAL: Direct array indexing for registers instead of _rd/_wr method calls in hot loop.

## 6. Comparison with Previous Benchmark (v1)

| Opcode | Previous ops/s | Current ops/s | Change |
|--------|---------------|----------------|--------|
| ADD | 1,506,869 | 1,506,296 | -0.0% |
| AND | 1,408,567 | 1,430,649 | +1.6% |
| DEC | 2,217,713 | 2,252,288 | +1.6% |
| INC | 2,076,932 | 2,311,853 | +11.3% |
| JMP | 6,086,327 | 6,449,917 | +6.0% |
| JNZ | 6,260,758 | 6,383,065 | +2.0% |
| LOAD | 990,491 | 1,037,097 | +4.7% |
| MOV | 1,158,874 | 1,220,497 | +5.3% |
| MUL | 1,443,823 | 1,450,215 | +0.4% |
| OR | 1,394,843 | 1,415,434 | +1.5% |
| POP | 1,170,848 | 1,174,813 | +0.3% |
| PUSH | 1,165,166 | 1,173,720 | +0.7% |
| STORE | 866,693 | 943,925 | +8.9% |
| SUB | 1,353,914 | 1,513,834 | +11.8% |
| XOR | 1,357,079 | 1,399,411 | +3.1% |
