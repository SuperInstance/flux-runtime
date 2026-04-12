# FLUX Runtime Performance Benchmark Report

**Date:** 2026-04-12 06:01:19 UTC
**Platform:** Linux x86_64
**Python:** 3.12.13
**Iterations:** 10,000 per benchmark (avg of 5 runs)

## 1. Instruction Decode Throughput

| Runtime | Instructions | Bytes | Time (s) | Ops/sec | Bytes/sec |
|---------|-------------|-------|----------|---------|-----------|
| python | 10,000 | 31,696 | 0.0043 | 11,636,288 | 36,882,378 |
| c | 10,000 | 10,001 | 0.0046 | 10,787,154 | 10,788,232 |

## 2. Execution Throughput by Opcode Category

| Runtime | Category | Opcodes | Iterations | Time (s) | Ops/sec | ns/op |
|---------|----------|---------|------------|----------|---------|-------|
| python | arithmetic | 9 | 10,000 | 0.0357 | 1,398,893 | 714.9 |
| c | arithmetic | 9 | 10,000 | 0.0050 | 9,970,563 | 100.3 |
| python | logic | 7 | 10,000 | 0.0344 | 1,451,643 | 688.9 |
| c | logic | 7 | 10,000 | 0.0042 | 11,928,779 | 83.8 |
| python | comparison | 4 | 10,000 | 0.0404 | 1,237,667 | 808.0 |
| c | comparison | 4 | 10,000 | 0.0047 | 10,694,638 | 93.5 |
| python | control_flow | 8 | 10,000 | 0.0083 | 6,050,185 | 165.3 |
| c | control_flow | 8 | 10,000 | 0.0039 | 12,697,116 | 78.8 |
| python | stack | 2 | 10,000 | 0.0223 | 2,246,591 | 445.1 |
| c | stack | 2 | 10,000 | 0.0042 | 11,931,691 | 83.8 |
| python | memory | 4 | 10,000 | 0.0531 | 941,055 | 1062.6 |
| c | memory | 4 | 10,000 | 0.0045 | 11,059,982 | 90.4 |
| python | data_movement | 6 | 10,000 | 0.0346 | 1,443,060 | 693.0 |
| c | data_movement | 6 | 10,000 | 0.0046 | 10,895,406 | 91.8 |

## 3. Memory Footprint

| Runtime | Phase | Memory |
|---------|-------|--------|
| python | empty_vm | 64.48 KB |
| python | loaded_program_1000ops | 64.48 KB |
| python | after_execution | 65.91 KB |
| python | vm_object_size | 48 B |
| python | memory_array_64kb | 64.06 KB |
| c | vm_struct_static | 96.35 KB |
| c | memory_array_64kb | 64.00 KB |
| c | stack_array_32kb | 32.00 KB |
| c | total_static | 96.35 KB |
| c | process_rss_kb | 24.48 MB |

## 4. Cross-Runtime Comparison (Python vs C)

| Benchmark | Python (ops/s) | C (ops/s) | Speedup |
|-----------|----------------|-----------|---------|
| decode_throughput | 11,636,288 | 10,787,154 | 0.9x |
| exec_arithmetic | 1,398,893 | 9,970,563 | 7.1x |
| exec_comparison | 1,237,667 | 10,694,638 | 8.6x |
| exec_control_flow | 6,050,185 | 12,697,116 | 2.1x |
| exec_data_movement | 1,443,060 | 10,895,406 | 7.5x |
| exec_logic | 1,451,643 | 11,928,779 | 8.2x |
| exec_memory | 941,055 | 11,059,982 | 11.8x |
| exec_stack | 2,246,591 | 11,931,691 | 5.3x |
| micro_MOVI | 2,102,811 | 10,931,296 | 5.2x |
| micro_ADD | 1,506,869 | 12,065,972 | 8.0x |
| micro_SUB | 1,353,914 | 11,155,998 | 8.2x |
| micro_MUL | 1,443,823 | 10,637,279 | 7.4x |
| micro_CMP_EQ | 1,294,072 | 11,100,930 | 8.6x |
| micro_JMP | 6,086,327 | 12,996,958 | 2.1x |
| micro_JNZ | 6,260,758 | 14,287,123 | 2.3x |
| micro_PUSH | 1,165,166 | 11,349,717 | 9.7x |
| micro_POP | 1,170,848 | 10,569,544 | 9.0x |
| micro_LOAD | 990,491 | 11,418,062 | 11.5x |
| micro_STORE | 866,693 | 10,055,197 | 11.6x |
| micro_MOV | 1,158,874 | 9,271,716 | 8.0x |
| micro_INC | 2,076,932 | 12,026,918 | 5.8x |
| micro_DEC | 2,217,713 | 12,690,494 | 5.7x |
| micro_AND | 1,408,567 | 11,445,487 | 8.1x |
| micro_OR | 1,394,843 | 10,071,830 | 7.2x |
| micro_XOR | 1,357,079 | 9,751,175 | 7.2x |
| micro_NOP | 6,074,360 | 10,022,067 | 1.6x |
| micro_HALT | 6,303,805 | 10,232,229 | 1.6x |
| micro_MOVI16 | 1,734,089 | 9,680,887 | 5.6x |

## 5. Opcode Microbenchmarks (Top 20)

| Opcode | Fmt | Python ops/s | Python ns/op | C ops/s | C ns/op | Speedup |
|--------|-----|--------------|--------------|---------|----------|---------|
| MOVI | D | 2,102,811 | 475.6 | 10,931,296 | 91.5 | 5.2x |
| ADD | E | 1,506,869 | 663.6 | 12,065,972 | 82.9 | 8.0x |
| SUB | E | 1,353,914 | 738.6 | 11,155,998 | 89.6 | 8.2x |
| MUL | E | 1,443,823 | 692.6 | 10,637,279 | 94.0 | 7.4x |
| CMP_EQ | E | 1,294,072 | 772.8 | 11,100,930 | 90.1 | 8.6x |
| JMP | F | 6,086,327 | 164.3 | 12,996,958 | 76.9 | 2.1x |
| JNZ | E | 6,260,758 | 159.7 | 14,287,123 | 70.0 | 2.3x |
| PUSH | B | 1,165,166 | 858.2 | 11,349,717 | 88.1 | 9.7x |
| POP | B | 1,170,848 | 854.1 | 10,569,544 | 94.6 | 9.0x |
| LOAD | E | 990,491 | 1009.6 | 11,418,062 | 87.6 | 11.5x |
| STORE | E | 866,693 | 1153.8 | 10,055,197 | 99.5 | 11.6x |
| MOV | E | 1,158,874 | 862.9 | 9,271,716 | 107.9 | 8.0x |
| INC | B | 2,076,932 | 481.5 | 12,026,918 | 83.1 | 5.8x |
| DEC | B | 2,217,713 | 450.9 | 12,690,494 | 78.8 | 5.7x |
| AND | E | 1,408,567 | 709.9 | 11,445,487 | 87.4 | 8.1x |
| OR | E | 1,394,843 | 716.9 | 10,071,830 | 99.3 | 7.2x |
| XOR | E | 1,357,079 | 736.9 | 9,751,175 | 102.6 | 7.2x |
| NOP | A | 6,074,360 | 164.6 | 10,022,067 | 99.8 | 1.6x |
| HALT | A | 6,303,805 | 158.6 | 10,232,229 | 97.7 | 1.6x |
| MOVI16 | F | 1,734,089 | 576.7 | 9,680,887 | 103.3 | 5.6x |

## Key Findings

- **Average C speedup over Python:** 6.7x
- **Best C speedup:** 11.8x
- **Worst C speedup:** 0.9x
- **Total benchmark categories:** 7
- **Total opcodes microbenchmarked:** 20
- **Instructions per decode benchmark:** 10,000
- **Instructions per exec benchmark:** 10,000
