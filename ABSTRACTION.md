primary_plane: 2
reads_from: [3, 4, 5]
writes_to: [2]
floor: 2
ceiling: 5
compilers:
  - name: deepseek-chat
    from: 4
    to: 2
    locks: 7
  - name: assembler
    from: 3
    to: 2
    locks: 0
reasoning: |
  FLUX Runtime is a Python bytecode interpreter. It operates at Plane 2
  (interpreted bytecode). It reads structured IR and domain language from
  above and executes bytecode. The VM itself is Python but the programs
  it runs are Plane 2 FLUX bytecode.
