from typing import Any, Dict


class Node:
    """Base node interface for simple graph runner."""

    def __init__(self, name: str):
        self.name = name

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the node logic. Must be implemented by subclasses."""
        raise NotImplementedError()


class Graph:
    """Tiny serial graph runner with explicit wiring.

    This is intentionally minimal: nodes are invoked in sequence determined by
    the `steps` list and each step receives the whole shared context dict.
    """

    def __init__(self):
        self.nodes = {}
        self.steps = []

    def add_node(self, node: Node):
        self.nodes[node.name] = node

    def add_step(self, node_name: str):
        if node_name not in self.nodes:
            raise KeyError(f"unknown node: {node_name}")
        self.steps.append(node_name)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ctx = context.copy() if isinstance(context, dict) else {}
        # allow nodes to share and augment context
        for name in self.steps:
            node = self.nodes[name]
            out = node.run(ctx)
            # store node output under context[name]
            ctx.setdefault("node_outputs", {})[name] = out
        return ctx
