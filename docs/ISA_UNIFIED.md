# FLUX Unified ISA — Complete Opcode Table

| Hex | Mnemonic | Fmt | Operands | Category | Source | Description |
|-----|----------|-----|----------|----------|--------|-------------|
| 0x00 | HALT | A | - | system | ✅ | Stop execution |
| 0x01 | NOP | A | - | system | ✅ | No operation (pipeline sync) |
| 0x02 | RET | A | - | system | 🔮 | Return from subroutine |
| 0x03 | IRET | A | - | system | ⚡ | Return from interrupt handler |
| 0x04 | BRK | A | - | debug | ✅ | Breakpoint (trap to debugger) |
| 0x05 | WFI | A | - | system | ⚡ | Wait for interrupt (low-power idle) |
| 0x06 | RESET | A | - | system | ⚡ | Soft reset of register file |
| 0x07 | SYN | A | - | system | ⚡ | Memory barrier / synchronize |
| 0x08 | INC | B | rd | arithmetic | ✅ | rd = rd + 1 |
| 0x09 | DEC | B | rd | arithmetic | ✅ | rd = rd - 1 |
| 0x0A | NOT | B | rd | arithmetic | ✅ | rd = ~rd (bitwise NOT) |
| 0x0B | NEG | B | rd | arithmetic | ✅ | rd = -rd (arithmetic negate) |
| 0x0C | PUSH | B | rd | stack | ✅ | Push rd onto stack |
| 0x0D | POP | B | rd | stack | ✅ | Pop stack into rd |
| 0x0E | CONF_LD | B | rd | confidence | ✅ | Load confidence register rd to accumulator |
| 0x0F | CONF_ST | B | rd | confidence | ✅ | Store confidence accumulator to register rd |
| 0x10 | SYS | C | imm8 | system | ✅ | System call with code imm8 |
| 0x11 | TRAP | C | imm8 | system | ⚡ | Software interrupt vector imm8 |
| 0x12 | DBG | C | imm8 | debug | ✅ | Debug print register imm8 |
| 0x13 | CLF | C | imm8 | system | 🔮 | Clear flags register bits imm8 |
| 0x14 | SEMA | C | imm8 | concurrency | ⚡ | Semaphore operation imm8 |
| 0x15 | YIELD | C | imm8 | concurrency | ✅ | Yield execution for imm8 cycles |
| 0x16 | CACHE | C | imm8 | system | ⚡ | Cache control (flush/invalidate by imm8) |
| 0x17 | STRIPCF | C | imm8 | confidence | ⚡ | Strip confidence from next imm8 ops |
| 0x18 | MOVI | D | rd, imm8 | move | ✅ | rd = sign_extend(imm8) |
| 0x19 | ADDI | D | rd, imm8 | arithmetic | ✅ | rd = rd + imm8 |
| 0x1A | SUBI | D | rd, imm8 | arithmetic | ✅ | rd = rd - imm8 |
| 0x1B | ANDI | D | rd, imm8 | logic | ✅ | rd = rd & imm8 |
| 0x1C | ORI | D | rd, imm8 | logic | ✅ | rd = rd | imm8 |
| 0x1D | XORI | D | rd, imm8 | logic | ✅ | rd = rd ^ imm8 |
| 0x1E | SHLI | D | rd, imm8 | shift | ✅ | rd = rd << imm8 |
| 0x1F | SHRI | D | rd, imm8 | shift | ✅ | rd = rd >> imm8 |
| 0x20 | ADD | E | rd, rs1, rs2 | arithmetic | ✅ | rd = rs1 + rs2 |
| 0x21 | SUB | E | rd, rs1, rs2 | arithmetic | ✅ | rd = rs1 - rs2 |
| 0x22 | MUL | E | rd, rs1, rs2 | arithmetic | ✅ | rd = rs1 * rs2 |
| 0x23 | DIV | E | rd, rs1, rs2 | arithmetic | ✅ | rd = rs1 / rs2 (signed) |
| 0x24 | MOD | E | rd, rs1, rs2 | arithmetic | ✅ | rd = rs1 % rs2 |
| 0x25 | AND | E | rd, rs1, rs2 | logic | ✅ | rd = rs1 & rs2 |
| 0x26 | OR | E | rd, rs1, rs2 | logic | ✅ | rd = rs1 | rs2 |
| 0x27 | XOR | E | rd, rs1, rs2 | logic | ✅ | rd = rs1 ^ rs2 |
| 0x28 | SHL | E | rd, rs1, rs2 | shift | ✅ | rd = rs1 << rs2 |
| 0x29 | SHR | E | rd, rs1, rs2 | shift | ✅ | rd = rs1 >> rs2 |
| 0x2A | MIN | E | rd, rs1, rs2 | arithmetic | ✅ | rd = min(rs1, rs2) |
| 0x2B | MAX | E | rd, rs1, rs2 | arithmetic | ✅ | rd = max(rs1, rs2) |
| 0x2C | CMP_EQ | E | rd, rs1, rs2 | compare | ✅ | rd = (rs1 == rs2) ? 1 : 0 |
| 0x2D | CMP_LT | E | rd, rs1, rs2 | compare | ✅ | rd = (rs1 < rs2) ? 1 : 0 |
| 0x2E | CMP_GT | E | rd, rs1, rs2 | compare | ✅ | rd = (rs1 > rs2) ? 1 : 0 |
| 0x2F | CMP_NE | E | rd, rs1, rs2 | compare | ✅ | rd = (rs1 != rs2) ? 1 : 0 |
| 0x30 | FADD | E | rd, rs1, rs2 | float | 🔮 | rd = f(rs1) + f(rs2) |
| 0x31 | FSUB | E | rd, rs1, rs2 | float | 🔮 | rd = f(rs1) - f(rs2) |
| 0x32 | FMUL | E | rd, rs1, rs2 | float | 🔮 | rd = f(rs1) * f(rs2) |
| 0x33 | FDIV | E | rd, rs1, rs2 | float | 🔮 | rd = f(rs1) / f(rs2) |
| 0x34 | FMIN | E | rd, rs1, rs2 | float | 🔮 | rd = fmin(rs1, rs2) |
| 0x35 | FMAX | E | rd, rs1, rs2 | float | 🔮 | rd = fmax(rs1, rs2) |
| 0x36 | FTOI | E | rd, rs1, - | convert | 🔮 | rd = int(f(rs1)) |
| 0x37 | ITOF | E | rd, rs1, - | convert | 🔮 | rd = float(rs1) |
| 0x38 | LOAD | E | rd, rs1, rs2 | memory | ✅ | rd = mem[rs1 + rs2] |
| 0x39 | STORE | E | rd, rs1, rs2 | memory | ✅ | mem[rs1 + rs2] = rd |
| 0x3A | MOV | E | rd, rs1, - | move | ✅ | rd = rs1 |
| 0x3B | SWP | E | rd, rs1, - | move | ✅ | swap(rd, rs1) |
| 0x3C | JZ | E | rd, rs1, - | control | ✅ | if rd == 0: pc += rs1 |
| 0x3D | JNZ | E | rd, rs1, - | control | ✅ | if rd != 0: pc += rs1 |
| 0x3E | JLT | E | rd, rs1, - | control | ✅ | if rd < 0: pc += rs1 |
| 0x3F | JGT | E | rd, rs1, - | control | ✅ | if rd > 0: pc += rs1 |
| 0x40 | MOVI16 | F | rd, imm16 | move | ✅ | rd = imm16 |
| 0x41 | ADDI16 | F | rd, imm16 | arithmetic | ✅ | rd = rd + imm16 |
| 0x42 | SUBI16 | F | rd, imm16 | arithmetic | ✅ | rd = rd - imm16 |
| 0x43 | JMP | F | rd, imm16 | control | ✅ | pc += imm16 (relative) |
| 0x44 | JAL | F | rd, imm16 | control | ✅ | rd = pc; pc += imm16 |
| 0x45 | CALL | F | rd, imm16 | control | ⚡ | push(pc); pc = rd + imm16 |
| 0x46 | LOOP | F | rd, imm16 | control | ⚡ | rd--; if rd > 0: pc -= imm16 |
| 0x47 | SELECT | F | rd, imm16 | control | 🔮 | pc += imm16 * rd (computed jump) |
| 0x48 | LOADOFF | G | rd, rs1, imm16 | memory | ✅ | rd = mem[rs1 + imm16] |
| 0x49 | STOREOF | G | rd, rs1, imm16 | memory | ✅ | mem[rs1 + imm16] = rd |
| 0x4A | LOADI | G | rd, rs1, imm16 | memory | ⚡ | rd = mem[mem[rs1] + imm16] |
| 0x4B | STOREI | G | rd, rs1, imm16 | memory | ⚡ | mem[mem[rs1] + imm16] = rd |
| 0x4C | ENTER | G | rd, rs1, imm16 | stack | ⚡ | push regs; sp -= imm16; rd=old_sp |
| 0x4D | LEAVE | G | rd, rs1, imm16 | stack | ⚡ | sp += imm16; pop regs; rd=ret |
| 0x4E | COPY | G | rd, rs1, imm16 | memory | ⚡ | memcpy(rd, rs1, imm16) |
| 0x4F | FILL | G | rd, rs1, imm16 | memory | ⚡ | memset(rd, rs1, imm16) |
| 0x50 | TELL | E | rd, rs1, rs2 | a2a | ✅ | Send rs2 to agent rs1, tag rd |
| 0x51 | ASK | E | rd, rs1, rs2 | a2a | ✅ | Request rs2 from agent rs1, resp→rd |
| 0x52 | DELEG | E | rd, rs1, rs2 | a2a | ✅ | Delegate task rs2 to agent rs1 |
| 0x53 | BCAST | E | rd, rs1, rs2 | a2a | ✅ | Broadcast rs2 to fleet, tag rd |
| 0x54 | ACCEPT | E | rd, rs1, rs2 | a2a | ✅ | Accept delegated task, ctx→rd |
| 0x55 | DECLINE | E | rd, rs1, rs2 | a2a | ✅ | Decline task with reason rs2 |
| 0x56 | REPORT | E | rd, rs1, rs2 | a2a | ✅ | Report task status rs2 to rd |
| 0x57 | MERGE | E | rd, rs1, rs2 | a2a | ✅ | Merge results from rs1,rs2→rd |
| 0x58 | FORK | E | rd, rs1, rs2 | a2a | ✅ | Spawn child agent, state→rd |
| 0x59 | JOIN | E | rd, rs1, rs2 | a2a | ✅ | Wait for child rs1, result→rd |
| 0x5A | SIGNAL | E | rd, rs1, rs2 | a2a | ✅ | Emit named signal rs2 on channel rd |
| 0x5B | AWAIT | E | rd, rs1, rs2 | a2a | ✅ | Wait for signal rs2, data→rd |
| 0x5C | TRUST | E | rd, rs1, rs2 | a2a | ✅ | Set trust level rs2 for agent rs1 |
| 0x5D | DISCOV | E | rd, rs1, rs2 | a2a | 🔮 | Discover fleet agents, list→rd |
| 0x5E | STATUS | E | rd, rs1, rs2 | a2a | ✅ | Query agent rs1 status, result→rd |
| 0x5F | HEARTBT | E | rd, rs1, rs2 | a2a | ✅ | Emit heartbeat, load→rd |
| 0x60 | C_ADD 🔒 | E | rd, rs1, rs2 | confidence | ✅ | rd = rs1+rs2, crd=min(crs1,crs2) |
| 0x61 | C_SUB 🔒 | E | rd, rs1, rs2 | confidence | ✅ | rd = rs1-rs2, crd=min(crs1,crs2) |
| 0x62 | C_MUL 🔒 | E | rd, rs1, rs2 | confidence | ✅ | rd = rs1*rs2, crd=crs1*crs2 |
| 0x63 | C_DIV 🔒 | E | rd, rs1, rs2 | confidence | ✅ | rd = rs1/rs2, crd=crs1*crs2*(1-ε) |
| 0x64 | C_FADD 🔒 | E | rd, rs1, rs2 | confidence | 🔮 | Float add + confidence propagation |
| 0x65 | C_FSUB 🔒 | E | rd, rs1, rs2 | confidence | 🔮 | Float sub + confidence propagation |
| 0x66 | C_FMUL 🔒 | E | rd, rs1, rs2 | confidence | 🔮 | Float mul + confidence propagation |
| 0x67 | C_FDIV 🔒 | E | rd, rs1, rs2 | confidence | 🔮 | Float div + confidence propagation |
| 0x68 | C_MERGE 🔒 | E | rd, rs1, rs2 | confidence | ✅ | Merge confidences: crd=weighted_avg |
| 0x69 | C_THRESH 🔒 | D | rd, imm8 | confidence | ✅ | Skip next if crd < imm8/255 |
| 0x6A | C_BOOST 🔒 | E | rd, rs1, rs2 | confidence | ⚡ | Boost crd by rs2 factor (max 1.0) |
| 0x6B | C_DECAY 🔒 | E | rd, rs1, rs2 | confidence | ⚡ | Decay crd by factor rs2 per cycle |
| 0x6C | C_SOURCE 🔒 | E | rd, rs1, rs2 | confidence | ⚡ | Set confidence source (sensor/model/human) |
| 0x6D | C_CALIB 🔒 | E | rd, rs1, rs2 | confidence | ✅ | Calibrate confidence against ground truth |
| 0x6E | C_EXPLY 🔒 | E | rd, rs1, rs2 | confidence | 🔮 | Apply confidence to control flow weight |
| 0x6F | C_VOTE 🔒 | E | rd, rs1, rs2 | confidence | ✅ | Weighted vote: crd = sum(crs*crs_i)/Σ |
| 0x70 | V_EVID | E | rd, rs1, rs2 | viewpoint | 🌐 | Evidentiality: source type rs2→rd |
| 0x71 | V_EPIST | E | rd, rs1, rs2 | viewpoint | 🌐 | Epistemic stance: certainty level |
| 0x72 | V_MIR | E | rd, rs1, rs2 | viewpoint | 🌐 | Mirative: unexpectedness marker |
| 0x73 | V_NEG | E | rd, rs1, rs2 | viewpoint | 🌐 | Negation scope: predicate vs proposition |
| 0x74 | V_TENSE | E | rd, rs1, rs2 | viewpoint | 🌐 | Temporal viewpoint alignment |
| 0x75 | V_ASPEC | E | rd, rs1, rs2 | viewpoint | 🌐 | Aspectual viewpoint: complete/ongoing |
| 0x76 | V_MODAL | E | rd, rs1, rs2 | viewpoint | 🌐 | Modal force: necessity/possibility |
| 0x77 | V_POLIT | E | rd, rs1, rs2 | viewpoint | 🌐 | Politeness register mapping |
| 0x78 | V_HONOR | E | rd, rs1, rs2 | viewpoint | 🌐 | Honorific level → trust tier |
| 0x79 | V_TOPIC | E | rd, rs1, rs2 | viewpoint | 🌐 | Topic-comment structure binding |
| 0x7A | V_FOCUS | E | rd, rs1, rs2 | viewpoint | 🌐 | Information focus marking |
| 0x7B | V_CASE | E | rd, rs1, rs2 | viewpoint | 🌐 | Case-based scope assignment |
| 0x7C | V_AGREE | E | rd, rs1, rs2 | viewpoint | 🌐 | Agreement (gender/number/person) |
| 0x7D | V_CLASS | E | rd, rs1, rs2 | viewpoint | 🌐 | Classifier→type mapping |
| 0x7E | V_INFL | E | rd, rs1, rs2 | viewpoint | 🌐 | Inflection→control flow mapping |
| 0x7F | V_PRAGMA | E | rd, rs1, rs2 | viewpoint | 🌐 | Pragmatic context switch |
| 0x80 | SENSE | E | rd, rs1, rs2 | sensor | ⚡ | Read sensor rs1, channel rs2→rd |
| 0x81 | ACTUATE | E | rd, rs1, rs2 | sensor | ⚡ | Write rd to actuator rs1, channel rs2 |
| 0x82 | SAMPLE | E | rd, rs1, rs2 | sensor | ⚡ | Sample ADC channel rs1, avg rs2→rd |
| 0x83 | ENERGY | E | rd, rs1, rs2 | sensor | ⚡ | Energy budget: available→rd, used→rs1 |
| 0x84 | TEMP | E | rd, rs1, rs2 | sensor | ⚡ | Temperature sensor read→rd |
| 0x85 | GPS | E | rd, rs1, rs2 | sensor | ⚡ | GPS coordinates→rd,rs1 |
| 0x86 | ACCEL | E | rd, rs1, rs2 | sensor | ⚡ | Accelerometer read (3-axis)→rd,rs1,rs2 |
| 0x87 | DEPTH | E | rd, rs1, rs2 | sensor | ⚡ | Depth/pressure sensor→rd |
| 0x88 | CAMCAP | E | rd, rs1, rs2 | sensor | ⚡ | Capture camera frame rs1→buffer rd |
| 0x89 | CAMDET | E | rd, rs1, rs2 | sensor | ⚡ | Run detection on buffer rd, N results→rs1 |
| 0x8A | PWM | E | rd, rs1, rs2 | sensor | ⚡ | PWM output: pin rs1, duty rd, freq rs2 |
| 0x8B | GPIO | E | rd, rs1, rs2 | sensor | ⚡ | GPIO: read/write pin rs1, direction rs2 |
| 0x8C | I2C | E | rd, rs1, rs2 | sensor | ⚡ | I2C: addr rs1, register rs2, data rd |
| 0x8D | SPI | E | rd, rs1, rs2 | sensor | ⚡ | SPI: send rd, receive→rd, cs=rs1 |
| 0x8E | UART | E | rd, rs1, rs2 | sensor | ⚡ | UART: send rd bytes from buf rs1 |
| 0x8F | CANBUS | E | rd, rs1, rs2 | sensor | ⚡ | CAN bus: send rd with ID rs1 |
| 0x90 | ABS | E | rd, rs1, - | math | ✅ | rd = |rs1| |
| 0x91 | SIGN | E | rd, rs1, - | math | ✅ | rd = sign(rs1) |
| 0x92 | SQRT | E | rd, rs1, - | math | 🔮 | rd = sqrt(rs1) |
| 0x93 | POW | E | rd, rs1, rs2 | math | 🔮 | rd = rs1 ^ rs2 |
| 0x94 | LOG2 | E | rd, rs1, - | math | 🔮 | rd = log2(rs1) |
| 0x95 | CLZ | E | rd, rs1, - | math | ⚡ | rd = count leading zeros(rs1) |
| 0x96 | CTZ | E | rd, rs1, - | math | ⚡ | rd = count trailing zeros(rs1) |
| 0x97 | POPCNT | E | rd, rs1, - | math | ⚡ | rd = popcount(rs1) |
| 0x98 | CRC32 | E | rd, rs1, rs2 | crypto | ⚡ | rd = crc32(rs1, rs2) |
| 0x99 | SHA256 | E | rd, rs1, rs2 | crypto | ✅ | SHA-256 block: msg rs1, len rs2→rd |
| 0x9A | RND | E | rd, rs1, rs2 | math | ✅ | rd = random in [rs1, rs2] |
| 0x9B | SEED | E | rd, rs1, - | math | ✅ | Seed PRNG with rs1 |
| 0x9C | FMOD | E | rd, rs1, rs2 | float | 🔮 | rd = fmod(rs1, rs2) |
| 0x9D | FSQRT | E | rd, rs1, - | float | 🔮 | rd = fsqrt(rs1) |
| 0x9E | FSIN | E | rd, rs1, - | float | 🔮 | rd = sin(rs1) |
| 0x9F | FCOS | E | rd, rs1, - | float | 🔮 | rd = cos(rs1) |
| 0xA0 | LEN | D | rd, imm8 | collection | 🔮 | rd = length of collection imm8 |
| 0xA1 | CONCAT | E | rd, rs1, rs2 | collection | 🔮 | rd = concat(rs1, rs2) |
| 0xA2 | AT | E | rd, rs1, rs2 | collection | 🔮 | rd = rs1[rs2] |
| 0xA3 | SETAT | E | rd, rs1, rs2 | collection | 🔮 | rs1[rs2] = rd |
| 0xA4 | SLICE | G | rd, rs1, imm16 | collection | 🔮 | rd = rs1[0:imm16] |
| 0xA5 | REDUCE | E | rd, rs1, rs2 | collection | 🔮 | rd = fold(rs1, rs2) |
| 0xA6 | MAP | E | rd, rs1, rs2 | collection | 🔮 | rd = map(rs1, fn rs2) |
| 0xA7 | FILTER | E | rd, rs1, rs2 | collection | 🔮 | rd = filter(rs1, fn rs2) |
| 0xA8 | SORT | E | rd, rs1, rs2 | collection | 🔮 | rd = sort(rs1, cmp rs2) |
| 0xA9 | FIND | E | rd, rs1, rs2 | collection | 🔮 | rd = index of rs2 in rs1 (-1=not found) |
| 0xAA | HASH | E | rd, rs1, rs2 | crypto | ✅ | rd = hash(rs1, algorithm rs2) |
| 0xAB | HMAC | E | rd, rs1, rs2 | crypto | ✅ | rd = hmac(rs1, key rs2) |
| 0xAC | VERIFY | E | rd, rs1, rs2 | crypto | ✅ | rd = verify sig rs2 on data rs1 |
| 0xAD | ENCRYPT | E | rd, rs1, rs2 | crypto | ✅ | rd = encrypt rs1 with key rs2 |
| 0xAE | DECRYPT | E | rd, rs1, rs2 | crypto | ✅ | rd = decrypt rs1 with key rs2 |
| 0xAF | KEYGEN | E | rd, rs1, rs2 | crypto | ✅ | rd = generate keypair, pub→rs1 priv→rs2 |
| 0xB0 | VLOAD | E | rd, rs1, rs2 | vector | ⚡ | Load vector from mem[rs1], len rs2 |
| 0xB1 | VSTORE | E | rd, rs1, rs2 | vector | ⚡ | Store vector rd to mem[rs1], len rs2 |
| 0xB2 | VADD | E | rd, rs1, rs2 | vector | ⚡ | Vector add: rd[i] = rs1[i] + rs2[i] |
| 0xB3 | VMUL | E | rd, rs1, rs2 | vector | ⚡ | Vector mul: rd[i] = rs1[i] * rs2[i] |
| 0xB4 | VDOT | E | rd, rs1, rs2 | vector | ⚡ | Dot product: rd = Σ rs1[i]*rs2[i] |
| 0xB5 | VNORM | E | rd, rs1, rs2 | vector | ⚡ | L2 norm: rd = sqrt(Σ rs1[i]²) |
| 0xB6 | VSCALE | E | rd, rs1, rs2 | vector | ⚡ | Scale: rd[i] = rs1[i] * rs2 (scalar) |
| 0xB7 | VMAXP | E | rd, rs1, rs2 | vector | ⚡ | Element-wise max: rd[i] = max(rs1,rs2) |
| 0xB8 | VMINP | E | rd, rs1, rs2 | vector | ⚡ | Element-wise min |
| 0xB9 | VREDUCE | E | rd, rs1, rs2 | vector | ⚡ | Reduce vector with op rs2 |
| 0xBA | VGATHER | E | rd, rs1, rs2 | vector | ⚡ | Gather: rd[i] = mem[rs1[rs2[i]]] |
| 0xBB | VSCATTER | E | rd, rs1, rs2 | vector | ⚡ | Scatter: mem[rs1[rs2[i]]] = rd[i] |
| 0xBC | VSHUF | E | rd, rs1, rs2 | vector | ⚡ | Shuffle lanes by index rs2 |
| 0xBD | VMERGE | E | rd, rs1, rs2 | vector | ⚡ | Merge vectors by mask rs2 |
| 0xBE | VCONF | E | rd, rs1, rs2 | vector | ⚡ | Vector confidence propagation |
| 0xBF | VSELECT | E | rd, rs1, rs2 | vector | ⚡ | Conditional select by confidence mask |
| 0xC0 | TMATMUL | E | rd, rs1, rs2 | tensor | ⚡ | Tensor matmul: rd = rs1 @ rs2 |
| 0xC1 | TCONV | E | rd, rs1, rs2 | tensor | ⚡ | 2D convolution: rd = conv(rs1, rs2) |
| 0xC2 | TPOOL | E | rd, rs1, rs2 | tensor | ⚡ | Max/avg pool: rd = pool(rs1, rs2) |
| 0xC3 | TRELU | E | rd, rs1, - | tensor | ⚡ | ReLU: rd = max(0, rs1) |
| 0xC4 | TSIGM | E | rd, rs1, - | tensor | ⚡ | Sigmoid: rd = 1/(1+exp(-rs1)) |
| 0xC5 | TSOFT | E | rd, rs1, rs2 | tensor | ⚡ | Softmax over dimension rs2 |
| 0xC6 | TLOSS | E | rd, rs1, rs2 | tensor | ⚡ | Loss function: type rs2, pred rs1 |
| 0xC7 | TGRAD | E | rd, rs1, rs2 | tensor | ⚡ | Gradient: rd = ∂loss/∂rs1, lr=rs2 |
| 0xC8 | TUPDATE | E | rd, rs1, rs2 | tensor | ⚡ | SGD update: rd -= rs2 * rs1 |
| 0xC9 | TADAM | E | rd, rs1, rs2 | tensor | ⚡ | Adam optimizer step |
| 0xCA | TEMBED | E | rd, rs1, rs2 | tensor | ⚡ | Embedding lookup: token rs1, table rs2 |
| 0xCB | TATTN | E | rd, rs1, rs2 | tensor | ⚡ | Self-attention: Q=rs1, K=V=rs2 |
| 0xCC | TSAMPLE | E | rd, rs1, rs2 | tensor | ⚡ | Sample from distribution rs1, temp rs2 |
| 0xCD | TTOKEN | E | rd, rs1, rs2 | tensor | 🔮 | Tokenize: text rs1, vocab rs2→rd |
| 0xCE | TDETOK | E | rd, rs1, rs2 | tensor | 🔮 | Detokenize: tokens rs1, vocab rs2→rd |
| 0xCF | TQUANT | E | rd, rs1, rs2 | tensor | ⚡ | Quantize: fp32 rs1 → int8, scale rs2 |
| 0xD0 | DMA_CPY | G | rd, rs1, imm16 | memory | ⚡ | DMA: copy imm16 bytes rd←rs1 |
| 0xD1 | DMA_SET | G | rd, rs1, imm16 | memory | ⚡ | DMA: fill imm16 bytes at rd with rs1 |
| 0xD2 | MMIO_R | G | rd, rs1, imm16 | memory | ⚡ | MMIO read: rd = io[rs1 + imm16] |
| 0xD3 | MMIO_W | G | rd, rs1, imm16 | memory | ⚡ | MMIO write: io[rs1 + imm16] = rd |
| 0xD4 | ATOMIC | G | rd, rs1, imm16 | memory | ⚡ | Atomic RMW: rd = swap(mem[rs1+imm16],rd) |
| 0xD5 | CAS | G | rd, rs1, imm16 | memory | ⚡ | Compare-and-swap at rs1+imm16 |
| 0xD6 | FENCE | G | rd, rs1, imm16 | memory | ⚡ | Memory fence: type imm16 (acq/rel/full) |
| 0xD7 | MALLOC | G | rd, rs1, imm16 | memory | 🔮 | Allocate imm16 bytes, handle→rd |
| 0xD8 | FREE | G | rd, rs1, imm16 | memory | 🔮 | Free allocation at rd |
| 0xD9 | MPROT | G | rd, rs1, imm16 | memory | ⚡ | Memory protect: rd=start, rs1=len, imm16=flags |
| 0xDA | MCACHE | G | rd, rs1, imm16 | memory | ⚡ | Cache management: op imm16, addr rd, len rs1 |
| 0xDB | GPU_LD | G | rd, rs1, imm16 | memory | ⚡ | GPU: load to device mem, offset imm16 |
| 0xDC | GPU_ST | G | rd, rs1, imm16 | memory | ⚡ | GPU: store from device mem |
| 0xDD | GPU_EX | G | rd, rs1, imm16 | compute | ⚡ | GPU: execute kernel rd, grid rs1, block imm16 |
| 0xDE | GPU_SYNC | G | rd, rs1, imm16 | compute | ⚡ | GPU: synchronize device imm16 |
| 0xDF | RESERVED_DF | G | - | reserved | — | Reserved |
| 0xE0 | JMPL | F | rd, imm16 | control | ✅ | Long relative jump: pc += imm16 |
| 0xE1 | JALL | F | rd, imm16 | control | ✅ | Long jump-and-link: rd = pc; pc += imm16 |
| 0xE2 | CALLL | F | rd, imm16 | control | ✅ | Long call: push(pc); pc = rd + imm16 |
| 0xE3 | TAIL | F | rd, imm16 | control | 🔮 | Tail call: pop frame; pc = rd + imm16 |
| 0xE4 | SWITCH | F | rd, imm16 | control | ⚡ | Context switch: save state, jump imm16 |
| 0xE5 | COYIELD | F | rd, imm16 | control | 🔮 | Coroutine yield: save, jump to imm16 |
| 0xE6 | CORESUM | F | rd, imm16 | control | 🔮 | Coroutine resume: restore, jump to rd |
| 0xE7 | FAULT | F | rd, imm16 | system | ⚡ | Raise fault code imm16, context rd |
| 0xE8 | HANDLER | F | rd, imm16 | system | ⚡ | Install fault handler at pc + imm16 |
| 0xE9 | TRACE | F | rd, imm16 | debug | ✅ | Trace: log rd, tag imm16 |
| 0xEA | PROF_ON | F | rd, imm16 | debug | ⚡ | Start profiling region imm16 |
| 0xEB | PROF_OFF | F | rd, imm16 | debug | ⚡ | End profiling region imm16 |
| 0xEC | WATCH | F | rd, imm16 | debug | ✅ | Watchpoint: break on write to rd+imm16 |
| 0xED | RESERVED_ED | F | - | reserved | — | Reserved |
| 0xEE | RESERVED_EE | F | - | reserved | — | Reserved |
| 0xEF | RESERVED_EF | F | - | reserved | — | Reserved |
| 0xF0 | HALT_ERR | A | - | system | ✅ | Halt with error (check flags) |
| 0xF1 | REBOOT | A | - | system | ⚡ | Warm reboot (preserve memory) |
| 0xF2 | DUMP | A | - | debug | ✅ | Dump register file to debug output |
| 0xF3 | ASSERT | A | - | debug | ✅ | Assert flags, halt if violation |
| 0xF4 | ID | A | - | system | 🔮 | Return agent ID to r0 |
| 0xF5 | VER | A | - | system | ✅ | Return ISA version to r0 |
| 0xF6 | CLK | A | - | system | ⚡ | Return clock cycle count to r0 |
| 0xF7 | PCLK | A | - | system | ⚡ | Return performance counter to r0 |
| 0xF8 | WDOG | A | - | system | ⚡ | Kick watchdog timer |
| 0xF9 | SLEEP | A | - | system | ⚡ | Enter low-power sleep (wake on interrupt) |
| 0xFA | RESERVED_FA | A | - | reserved | — | Reserved |
| 0xFB | RESERVED_FB | A | - | reserved | — | Reserved |
| 0xFC | RESERVED_FC | A | - | reserved | — | Reserved |
| 0xFD | RESERVED_FD | A | - | reserved | — | Reserved |
| 0xFE | RESERVED_FE | A | - | reserved | — | Reserved |
| 0xFF | ILLEGAL | A | - | system | ✅ | Illegal instruction trap |

**Total:** 247 defined, 9 reserved = 256 slots
**Confidence ops:** 16