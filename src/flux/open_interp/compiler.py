"""
Flux Compiler-Compiler — agents build their own domain-specific interpreter.

Takes a set of .fluxvocab files and produces a compiled Python module
that natively speaks those vocabulary words. No pattern-matching overhead
at runtime — the words ARE the functions.

Usage:
    from flux.open_interp.compiler import compile_interpreter
    
    # Agent creates a domain-specific runtime
    compile_interpreter(
        vocab_folders=["vocabularies/math", "vocabularies/autopilot"],
        output="autopilot_runtime.py",
        class_name="AutopilotFlux"
    )
    
    # Now agents use it directly
    from autopilot_runtime import AutopilotFlux
    rt = AutopilotFlux()
    result = rt.run("steer to heading 270")
"""

import os
import re
from typing import List, Optional
from .vocabulary import Vocabulary


def compile_interpreter(
    vocab_folders: List[str],
    output: str,
    class_name: str = "CustomFlux",
    description: str = "",
    author: str = "",
) -> str:
    """
    Compile vocabulary folders into a standalone Python interpreter module.
    
    The generated module has:
    - A method for each vocabulary pattern (named from the pattern)
    - A run() method that auto-matches text to methods
    - A sandbox for safe execution
    - No external dependencies
    
    Returns the path to the generated file.
    """
    vocab = Vocabulary()
    for folder in vocab_folders:
        vocab.load_folder(folder)
    
    lines = []
    lines.append('"""')
    lines.append(f'{class_name} — Domain-Specific FLUX Runtime')
    if description:
        lines.append(f'{description}')
    if author:
        lines.append(f'Compiled by: {author}')
    lines.append(f'Vocabularies: {", ".join(vocab_folders)}')
    lines.append(f'Patterns: {len(vocab.entries)}')
    lines.append('"""')
    lines.append('')
    lines.append('import struct')
    lines.append('from typing import Optional, Dict, List')
    lines.append('')
    
    # SandboxVM inline (no external deps)
    lines.append('# Sandbox VM (inline — no dependencies)')
    lines.append('class _VM:')
    lines.append('    def __init__(self, bc, max_cycles=1000000):')
    lines.append('        self.bc=bc; self.gp=[0]*16; self.pc=0; self.halted=False')
    lines.append('        self.cycles=0; self.max_cycles=max_cycles; self.stack=[]')
    lines.append('    def _u8(self):')
    lines.append('        v=self.bc[self.pc]; self.pc+=1; return v')
    lines.append('    def _i16(self):')
    lines.append('        lo=self.bc[self.pc]; hi=self.bc[self.pc+1]; self.pc+=2')
    lines.append('        val=lo|(hi<<8)')
    lines.append('        return val-65536 if val>=32768 else val')
    lines.append('    def execute(self):')
    lines.append('        try:')
    lines.append('            while not self.halted and self.pc<len(self.bc) and self.cycles<self.max_cycles:')
    lines.append('                op=self._u8(); self.cycles+=1')
    lines.append('                if op==0x80: self.halted=True')
    lines.append('                elif op==0x01: d,s=self._u8(),self._u8(); self.gp[d]=self.gp[s]')
    lines.append('                elif op==0x2B: d=self._u8(); self.gp[d]=self._i16()')
    lines.append('                elif op==0x08: d,a,b=self._u8(),self._u8(),self._u8(); self.gp[d]=self.gp[a]+self.gp[b]')
    lines.append('                elif op==0x09: d,a,b=self._u8(),self._u8(),self._u8(); self.gp[d]=self.gp[a]-self.gp[b]')
    lines.append('                elif op==0x0A: d,a,b=self._u8(),self._u8(),self._u8(); self.gp[d]=self.gp[a]*self.gp[b]')
    lines.append('                elif op==0x0B: d,a,b=self._u8(),self._u8(),self._u8(); self.gp[d]=int(self.gp[a]/self.gp[b])')
    lines.append('                elif op==0x0E: self.gp[self._u8()]+=1')
    lines.append('                elif op==0x0F: self.gp[self._u8()]-=1')
    lines.append("                elif op==0x06: d=self._u8(); off=self._i16(); exec('self.pc+=off' if self.gp[d]!=0 else '')")
    lines.append("                elif op==0x2E: d=self._u8(); off=self._i16(); exec('self.pc+=off' if self.gp[d]==0 else '')")
    lines.append('                elif op==0x2D: a,b=self._u8(),self._u8(); self.gp[13]=(self.gp[a]>self.gp[b])-(self.gp[a]<self.gp[b])')
    lines.append('        except: pass')
    lines.append('        return self')
    lines.append('')
    
    # Assembler inline
    lines.append('def _asm(text):')
    lines.append('    bc=bytearray()')
    lines.append('    OPCODES={"NOP":0x00,"MOV":0x01,"MOVI":0x2B,"IADD":0x08,"ISUB":0x09,"IMUL":0x0A,"IDIV":0x0B,"INC":0x0E,"DEC":0x0F,"JNZ":0x06,"JZ":0x2E,"CMP":0x2D,"HALT":0x80}')
    lines.append('    for line in text.split(chr(10)):')
    lines.append('        line=line.strip()')
    lines.append('        if not line or line.startswith(";"): continue')
    lines.append('        p=line.replace(","," ").split()')
    lines.append('        mn=p[0].upper()')
    lines.append('        if mn not in OPCODES: continue')
    lines.append('        op=OPCODES[mn]')
    lines.append('        if mn in ("HALT","NOP"): bc.append(op)')
    lines.append('        elif mn in ("INC","DEC"): bc.append(op); bc.append(int(p[1][1:]))')
    lines.append('        elif mn in ("MOV",): bc.append(op); bc.append(int(p[1][1:])); bc.append(int(p[2][1:]))')
    lines.append('        elif mn in ("IADD","ISUB","IMUL","IDIV","CMP"): bc.append(op); bc.append(int(p[1][1:])); bc.append(int(p[2][1:])); bc.append(int(p[3][1:]) if len(p)>3 else int(p[2][1:]))')
    lines.append('        elif mn in ("MOVI","JNZ","JZ"): bc.append(op); bc.append(int(p[1][1:])); bc.extend(struct.pack("<h",int(p[2])))')
    lines.append('    return bytes(bc)')
    lines.append('')
    
    # Result class
    lines.append('class Result:')
    lines.append('    def __init__(self, success=True, value=None, cycles=0, error=None):')
    lines.append('        self.success=success; self.value=value; self.cycles=cycles; self.error=error')
    lines.append('    def __repr__(self):')
    lines.append('        return f"Result({self.value})" if self.success else f"Error({self.error})"')
    lines.append('')
    
    # Main class header + __init__ with pattern registrations
    lines.append(f'class {class_name}:')
    lines.append(f'    """Domain-specific FLUX runtime with {len(vocab.entries)} vocabulary patterns."""')
    lines.append('    ')
    lines.append('    def __init__(self):')
    lines.append('        import re')
    lines.append('        self._patterns = []')
    
    # Generate methods and collect init registrations
    method_names = set()
    method_lines = []  # method definitions (go after __init__)
    init_lines = []   # pattern registrations (go inside __init__)
    
    for i, entry in enumerate(vocab.entries):
        safe_name = re.sub(r'[^a-z0-9_]', '_', entry.name.lower())
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        if not safe_name or safe_name in method_names:
            safe_name = f"word_{i}"
        method_names.add(safe_name)
        
        # Method definition
        method_lines.append(f'    ')
        method_lines.append(f'    def {safe_name}(self, **kwargs):')
        method_lines.append(f'        """{entry.description or entry.pattern}"""')
        method_lines.append(f'        asm = """{entry.bytecode_template}"""')
        method_lines.append(f'        for k, v in kwargs.items():')
        method_lines.append(f'            asm = asm.replace("${{"+k+"}}", str(v))')
        method_lines.append(f'        bc = _asm(asm)')
        method_lines.append(f'        vm = _VM(bc).execute()')
        method_lines.append(f'        return Result(success=vm.halted, value=vm.gp[{entry.result_reg}], cycles=vm.cycles)')
        
        # Pattern registration (inside __init__)
        # Build regex same way as vocabulary.py: split on $var, escape literals
        vparts = re.split(r'(\$\w+)', entry.pattern)
        rparts = []
        for vp in vparts:
            if vp.startswith('$'):
                rparts.append(f'(?P<{vp[1:]}>\\d+)')
            else:
                rparts.append(re.escape(vp))
        regex_str = ''.join(rparts)
        init_lines.append(f'        self._patterns.append((re.compile(r"{regex_str}", re.IGNORECASE), self.{safe_name}))')
    
    # Write __init__ body (registrations), then methods
    for il in init_lines:
        lines.append(il)
    for ml in method_lines:
        lines.append(ml)
    
    # run() method — auto-match
    lines.append('    ')
    lines.append('    def run(self, text: str) -> Result:')
    lines.append('        """Run natural language text against compiled vocabulary."""')
    lines.append('        for pattern, method in self._patterns:')
    lines.append('            m = pattern.search(text)')
    lines.append('            if m:')
    lines.append('                return method(**{k: v for k, v in m.groupdict().items() if v is not None})')
    lines.append('        return Result(success=False, error=f"No match for: {text[:80]}")')
    
    # Write the file
    content = '\n'.join(lines)
    with open(output, 'w') as f:
        f.write(content)
    
    return output
