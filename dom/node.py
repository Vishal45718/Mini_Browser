from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class Node:
    node_type: str  # 'element' | 'text' | 'document'
    tag_name: str = ''
    attributes: Dict[str, str] = field(default_factory=dict)
    text: str = ''
    children: List['Node'] = field(default_factory=list)
    parent: Optional['Node'] = field(default=None, repr=False)

    def append_child(self, child: 'Node'):
        child.parent = self
        self.children.append(child)

    def get_attr(self, name: str) -> str:
        return self.attributes.get(name, '')

    # Simple pretty-print for debugging
    def dump(self, indent=0):
        prefix = '  ' * indent
        if self.node_type == 'text':
            text_preview = self.text.strip()
            if text_preview:
                print(f"{prefix}[text: {text_preview!r}]")
        else:
            attr_str = "".join([f' {k}="{v}"' for k, v in self.attributes.items()])
            print(f"{prefix}<{self.tag_name}{attr_str}>")
            for child in self.children:
                child.dump(indent + 1)
