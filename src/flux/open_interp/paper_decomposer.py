"""
Paper Decomposer — Research Papers → FLUX Vocabulary

Reads a directory of research papers (.md files) and extracts named concepts,
formulas, and key innovations into FLUX vocabulary entries.

This is how Cocapn intellectual property becomes words that any agent can learn.
The papers become vocabulary. The vocabulary becomes bytecode. The bytecode
becomes execution. Ideas become operational.

Usage:
    from flux.open_interp.paper_decomposer import PaperDecomposer

    pd = PaperDecomposer()
    vocab = pd.decompose_papers("/path/to/papers")
    vocab.save("vocabularies/custom/papers.fluxvocab")

    # Or decompose a single paper
    vocab = pd.decompose_file("papers/01-origin-centric-data-systems/README.md")
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from .decomposer import DecomposedVocabulary


class PaperSection:
    """A section extracted from a paper."""
    def __init__(self, title: str, level: int, content: str, formulas: List[str] = None):
        self.title = title
        self.level = level
        self.content = content
        self.formulas = formulas or []
    
    @property
    def is_concept(self) -> bool:
        """Is this a named concept worth extracting?"""
        # Level 2-3 headings with substantial content
        if self.level > 3:
            return False
        if len(self.content.strip()) < 50:
            return False
        # Skip generic headings
        skip = {'overview', 'introduction', 'conclusion', 'references', 'see also',
                'external links', 'further reading', 'bibliography', 'appendix'}
        return self.title.lower().strip() not in skip


class PaperDecomposer:
    """
    Decomposes research papers into FLUX vocabulary patterns.
    
    Extracts:
    - Named concepts from headings
    - Mathematical formulas and their descriptions
    - Key innovations and contributions
    - Tuple definitions and formal systems
    - Performance claims and metrics
    
    Each concept becomes a vocabulary entry with a natural language pattern
    in FLUX-ese that any agent can learn and use.
    """
    
    def __init__(self):
        self.papers_processed = 0
        self.concepts_found = 0
    
    def decompose_papers(self, directory: str) -> DecomposedVocabulary:
        """Decompose all papers in a directory into vocabulary."""
        entries = []
        
        for root, dirs, files in os.walk(directory):
            for fname in sorted(files):
                if fname.endswith('.md') and not fname.startswith('.'):
                    fpath = os.path.join(root, fname)
                    paper_name = os.path.basename(os.path.dirname(fpath))
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        paper_entries = self._process_paper(content, paper_name)
                        entries.extend(paper_entries)
                        self.papers_processed += 1
                    except Exception:
                        continue
        
        self.concepts_found = len(entries)
        
        return DecomposedVocabulary(
            module_name=f"papers:{os.path.basename(directory)}",
            entries=entries,
            metadata={
                "papers_processed": self.papers_processed,
                "concepts_extracted": self.concepts_found,
            }
        )
    
    def decompose_file(self, filepath: str) -> DecomposedVocabulary:
        """Decompose a single paper file."""
        paper_name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        entries = self._process_paper(content, paper_name)
        self.concepts_found = len(entries)
        
        return DecomposedVocabulary(
            module_name=f"paper:{paper_name}",
            entries=entries,
        )
    
    def _process_paper(self, content: str, paper_name: str) -> List[Dict]:
        """Extract vocabulary entries from a single paper."""
        sections = self._parse_sections(content)
        entries = []
        
        # Extract paper-level concept from title
        title_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        if title_match:
            paper_title = title_match.group(1).strip()
            # Clean up emoji and formatting
            paper_title = re.sub(r'[📊📐📈🤖🔷🌍⚛️⚡🚀🎯💡]', '', paper_title).strip()
            
            # Extract key formulas from entire paper
            formulas = self._extract_formulas(content)
            
            # Extract key innovations
            innovations = self._extract_innovations(content)
            
            # Create entry for the paper's main concept
            pattern = self._title_to_pattern(paper_title)
            if pattern:
                desc = self._extract_description(content)
                tags = self._extract_tags(paper_name, content)
                
                entries.append({
                    "pattern": pattern,
                    "assembly": "MOVI R0, 0\nHALT",  # Native bridge placeholder
                    "result_reg": 0,
                    "name": self._title_to_name(paper_title),
                    "description": desc[:200],
                    "tags": tags,
                    "native_call": True,
                    "python_fn": f"papers.{paper_name}",
                    "source_paper": paper_name,
                    "formulas": formulas[:3],  # Top 3 formulas
                    "innovations": innovations[:3],
                })
        
        # Extract sub-concepts from sections
        for section in sections:
            if section.is_concept and len(entries) < 15:  # Cap per paper
                pattern = self._section_to_pattern(section)
                if pattern:
                    entries.append({
                        "pattern": pattern,
                        "assembly": "MOVI R0, 0\nHALT",
                        "result_reg": 0,
                        "name": self._title_to_name(section.title),
                        "description": section.content[:200].strip(),
                        "tags": ["concept", paper_name],
                        "native_call": True,
                        "python_fn": f"papers.{paper_name}.{self._title_to_name(section.title)}",
                        "source_paper": paper_name,
                    })
        
        return entries
    
    def _parse_sections(self, content: str) -> List[PaperSection]:
        """Parse markdown content into sections."""
        sections = []
        lines = content.split('\n')
        current_title = ""
        current_level = 0
        current_lines = []
        
        for line in lines:
            heading = re.match(r'^(#{1,4})\s+(.+)$', line)
            if heading:
                # Save previous section
                if current_title:
                    sections.append(PaperSection(
                        title=current_title,
                        level=current_level,
                        content='\n'.join(current_lines),
                        formulas=self._extract_formulas('\n'.join(current_lines)),
                    ))
                current_title = heading.group(2).strip()
                current_level = len(heading.group(1))
                current_lines = []
            else:
                current_lines.append(line)
        
        # Save last section
        if current_title:
            sections.append(PaperSection(
                title=current_title,
                level=current_level,
                content='\n'.join(current_lines),
            ))
        
        return sections
    
    def _extract_formulas(self, text: str) -> List[str]:
        """Extract mathematical formulas."""
        formulas = []
        
        # $$...$$ blocks
        for m in re.finditer(r'\$\$(.+?)\$\$', text, re.DOTALL):
            formulas.append(m.group(1).strip())
        
        # `...` inline code that looks like math
        for m in re.finditer(r'`([A-Za-z_]+\([^)]+\)|[A-Z]\s*[=∈⊂∪∩].*?)`', text):
            formulas.append(m.group(1).strip())
        
        # X = (A, B, C) tuple definitions
        for m in re.finditer(r'([A-Zα-ωΑ-Ω]+)\s*=\s*\(([^)]+)\)', text):
            formulas.append(f"{m.group(1)} = ({m.group(2)})")
        
        return formulas[:5]  # Cap at 5
    
    def _extract_innovations(self, text: str) -> List[str]:
        """Extract key innovations and contributions."""
        innovations = []
        
        # Look for innovation/contribution markers
        patterns = [
            r'(?:Key Innovation|Major Contribution|Core Innovation)[:\s]+(.+?)(?:\n|$)',
            r'\*\*(.+?)\*\*:\s*(?:Eliminat|Achiev|Reduc|Transform|Revolution| Scalab|Breakthrough)',
            r'-\s+\*\*(.+?)\*\*\s*-',
        ]
        
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                innov = m.group(1).strip()
                if len(innov) > 5 and len(innov) < 200:
                    innovations.append(innov)
        
        return innovations[:5]
    
    def _extract_description(self, content: str) -> str:
        """Extract the first substantive paragraph."""
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Find first paragraph after title that's not a table or heading
            stripped = line.strip()
            if (stripped and not stripped.startswith('#') and not stripped.startswith('|')
                and not stripped.startswith('---') and not stripped.startswith('!')
                and not stripped.startswith('*Paper') and len(stripped) > 40):
                # Collect until empty line
                desc_lines = [stripped]
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith('#') or next_line.startswith('|'):
                        break
                    desc_lines.append(next_line)
                return ' '.join(desc_lines)
        return ""
    
    def _extract_tags(self, paper_name: str, content: str) -> List[str]:
        """Extract category tags."""
        tags = ["paper", paper_name]
        
        # Look for category keywords in content
        categories = {
            'distributed': 'distributed', 'consensus': 'consensus',
            'memory': 'memory', 'confidence': 'confidence',
            'agent': 'agents', 'tensor': 'tensors',
            'geometric': 'geometry', 'game': 'game-theory',
            'thermal': 'thermal', 'gpu': 'gpu',
            'edge': 'edge-computing', 'bytecode': 'bytecode',
            'tile': 'tile-algebra', 'stigmerg': 'stigmergy',
            'emergen': 'emergence', 'causal': 'causal',
            'neuromorphic': 'neuromorphic', 'adversarial': 'adversarial',
        }
        
        content_lower = content[:2000].lower()
        for keyword, tag in categories.items():
            if keyword in content_lower:
                tags.append(tag)
        
        return tags[:5]
    
    def _title_to_pattern(self, title: str) -> str:
        """Convert a paper title to a FLUX-ese pattern."""
        # Clean
        title = re.sub(r'[📊📐📈🤖🔷🌍⚛️⚡🚀🎯💡:\-–—]', '', title).strip()
        
        # Remove "Paper N:" prefix
        title = re.sub(r'^Paper\s+\d+:\s*', '', title, flags=re.IGNORECASE)
        
        # Generate pattern
        name_lower = title.lower().strip()
        
        # Specific patterns for known concepts
        pattern_map = {
            'origin-centric': 'track origin of $data',
            'confidence cascade': 'confidence cascade for $value with deadband $delta',
            'tile algebra': 'compose tile $a with tile $b',
            'rate-based': 'detect rate change for $value',
            'stigmergic': 'stigmergic coordinate $signal',
            'pythagorean': 'geometric tensor for $rotation',
            'game-theory': 'game theory solve for $players',
            'neuromorphic': 'neuromorphic process $signal',
            'thermal': 'thermal manage $workload',
            'bytecode': 'compile to bytecode $source',
            'distributed consensus': 'consensus among $agents',
            'multi-modal': 'fuse modalities $data',
            'adversarial': 'adversarial defend $model',
            'structural memory': 'structural memory for $system',
            'emergence': 'detect emergence in $population',
            'causal': 'causal trace for $event',
            'edge-to-cloud': 'edge to cloud migrate $workload',
            'energy harvest': 'energy harvest for $device',
            'self-play': 'self-play train $agent',
            'hydraulic': 'hydraulic intelligence for $flow',
            'value network': 'value network for $decisions',
            'smpbot': 'breed agent from $model and $seed',
            'laminar': 'laminar flow check for $process',
            'geometric encoding': 'geometric encode $state',
            'fps paradigm': 'first-person agent in $environment',
        }
        
        for key, pattern in pattern_map.items():
            if key in name_lower:
                return pattern
        
        # Generic: "analyze [topic] for $params"
        words = title.split()
        if len(words) <= 4:
            return f"{name_lower} for $params"
        return f"{name_lower[:30]} analyze $params"
    
    def _title_to_name(self, title: str) -> str:
        """Convert a title to a safe name."""
        name = re.sub(r'[📊📐📈🤖🔷🌍⚛️⚡🚀🎯💡:\-–—\s]+', '_', title)
        name = re.sub(r'[^a-zA-Z0-9_]', '', name)
        name = re.sub(r'_+', '_', name).strip('_').lower()
        return name[:40]
    
    def _section_to_pattern(self, section: PaperSection) -> Optional[str]:
        """Convert a section to a pattern if it's extractable."""
        title = section.title.strip()
        
        # Skip if too short or too generic
        if len(title) < 5:
            return None
        
        # Clean section title
        clean = re.sub(r'[📊📐📈🤖🔷🌍⚛️⚡🚀🎯💡]', '', title).strip()
        clean_lower = clean.lower()
        
        skip_words = {'overview', 'statistics', 'table', 'figure', 'see also', 'reference', 'citation'}
        if any(w in clean_lower for w in skip_words):
            return None
        
        # Generate: "concept_name $params"
        words = clean_lower.split()
        # Take first 3 words max
        name_parts = []
        for w in words[:3]:
            if re.match(r'^[a-z]+$', w):
                name_parts.append(w)
        
        if name_parts:
            return f"{' '.join(name_parts)} $params"
        return None
