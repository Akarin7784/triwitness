#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p graphix/graphsim
cat > graphix/graphsim/rxgraphstate.py <<'TW_EOF'
"""Graph state simulator implemented with rustworkx."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .basegraphstate import RUSTWORKX_INSTALLED, BaseGraphState
from .rxgraphviews import EdgeList, NodeList

if TYPE_CHECKING:
    from collections.abc import Iterator

if RUSTWORKX_INSTALLED:
    import rustworkx as rx
else:
    rx = None


class RXGraphState(BaseGraphState):
    """Graph state simulator implemented with rustworkx.

    See :class:`~graphix.graphsim.basegraphstate.BaseGraphState` for more details.
    """

    def __init__(
        self,
        nodes: list[int] | None = None,
        edges: list[tuple[int, int]] | None = None,
        vops: dict[int, int] | None = None,
    ):
        """Initialize graph state simulator.

        Parameters
        ----------
        nodes : list[int]
            A container of nodes (list, dict, etc)
        edges : list[tuple[int, int]]
            list of tuples (i,j) for pairs to be entangled.
        vops : dict[int, int]
            dict of local Clifford gates with keys for node indices and
            values for Clifford index (see graphix.clifford.CLIFFORD)
        """
        super().__init__()
        self._graph = rx.PyGraph()
        self._nodes = NodeList()
        self._edges = EdgeList()
        if nodes is not None:
            self.add_nodes_from(nodes)
        if edges is not None:
            self.add_edges_from(edges)
        if vops is not None:
            self.apply_vops(vops)

    @property
    def nodes(self) -> NodeList:
        """Return the set of nodes."""
        return self._nodes

    @property
    def edges(self) -> EdgeList:
        """Return the set of edges."""
        return self._edges

    @property
    def graph(self) -> rx.PyGraph:
        """Return the graph itself."""
        return self._graph

    def degree(self) -> Iterator[tuple[int, int]]:
        """Return an iterator for (node, degree) tuples, where degree is the number of edges adjacent to the node."""
        ret = []
        for n in self.nodes:
            nidx = self.nodes.get_node_index(n)
            degree = self._graph.degree(nidx)
            ret.append((n, degree))
        return iter(ret)

    def neighbors(self, node) -> Iterator[int]:
        """Return an iterator over all neighbors of node n.

        See :meth:`BaseGraphState.neighbors`.
        """
        nidx = self.nodes.get_node_index(node)
        return (self.nodes.idx_to_num[idx] for idx in self._graph.neighbors(nidx))

    def subgraph(self, nodes: list) -> rx.PyGraph:
        """Return a subgraph of the graph.

        See :meth:`BaseGraphState.subgraph`.
        """
        nidx = [self.nodes.get_node_index(n) for n in nodes]
        return self._graph.subgraph(nidx)

    def number_of_edges(self, u: int | None = None, v: int | None = None) -> int:
        """Return the number of edges between two nodes.

        See :meth:`BaseGraphState.number_of_edges`.
        """
        if u is None and v is None:
            return len(self.edges)
        elif u is None or v is None:
            raise ValueError("u and v must be specified together")
        uidx = self.nodes.get_node_index(u)
        vidx = self.nodes.get_node_index(v)
        return len(self._graph.get_all_edge_data(uidx, vidx))

    def adjacency(self) -> Iterator:
        """Return an iterator over (node, adjacency dict) tuples for all nodes.

        See :meth:`BaseGraphState.adjacency`.
        """
        ret = []
        for n in self.nodes:
            nidx = self.nodes.get_node_index(n)
            adjacency_dict = self._graph.adj(nidx)
            new_adjacency_dict = {}
            for nidx in adjacency_dict.keys():
                new_adjacency_dict[self.nodes.get_node_index(nidx)] = {}  # replace None with {}
            ret.append((n, new_adjacency_dict))
        return iter(ret)

    def remove_node(self, node: int) -> None:
        """Remove a node from the graph.

        See :meth:`BaseGraphState.remove_node`.
        """
        nidx = self.nodes.get_node_index(node)
        self._graph.remove_node(nidx)
        self.nodes.remove_node(node)
        self.edges.remove_edges_by_node(node)

    def remove_nodes_from(self, nodes: list[int]) -> None:
        """Remove all nodes specified in the list.

        See :meth:`BaseGraphState.remove_nodes_from`.
        """
        for n in nodes:
            self.remove_node(n)

    def remove_edge(self, u: int, v: int) -> None:
        """Remove an edge from the graph.

        See :meth:`BaseGraphState.remove_edge`.
        """
        uidx = self.nodes.get_node_index(u)
        vidx = self.nodes.get_node_index(v)
        self._graph.remove_edge(uidx, vidx)
        self.edges.remove_edge((u, v))

    def remove_edges_from(self, edges: list[tuple[int, int]]) -> None:
        """Remove all edges specified in the list.

        See :meth:`BaseGraphState.remove_edges_from`.
        """
        for e in edges:
            self.remove_edge(e[0], e[1])

    def add_nodes_from(self, nodes: list[int]):
        """Add nodes and initialize node properties.

        See :meth:`BaseGraphState.add_nodes_from`.
        """
        node_indices = self._graph.add_nodes_from([(n, {"loop": False, "sign": False, "hollow": False}) for n in nodes])
        for nidx in node_indices:
            self.nodes.add_node(self._graph[nidx][0], self._graph[nidx][1], nidx)

    def add_edges_from(self, edges):
        """Add edges and initialize node properties of newly added nodes.

        See :meth:`BaseGraphState.add_edges_from`.
        """
        for u, v in edges:
            # adding edges may add new nodes
            if u not in self.nodes:
                nidx = self._graph.add_node((u, {"loop": False, "sign": False, "hollow": False}))
                self.nodes.add_node(self._graph[nidx][0], self._graph[nidx][1], nidx)
            if v not in self.nodes:
                nidx = self._graph.add_node((v, {"loop": False, "sign": False, "hollow": False}))
                self.nodes.add_node(self._graph[nidx][0], self._graph[nidx][1], nidx)
            uidx = self.nodes.get_node_index(u)
            vidx = self.nodes.get_node_index(v)
            eidx = self._graph.add_edge(uidx, vidx, None)
            self.edges.add_edge((self._graph[uidx][0], self._graph[vidx][0]), None, eidx)

    def local_complement(self, node):
        """Perform local complementation of a graph.

        See :meth:`BaseGraphState.local_complement`.
        """
        g = self.subgraph(list(self.neighbors(node)))
        g_new = rx.complement(g)
        g_edge_list = []
        for uidx, vidx in g.edge_list():
            u = g.get_node_data(uidx)[0]
            v = g.get_node_data(vidx)[0]
            g_edge_list.append((u, v))
        g_new_eidx_list = []
        for uidx, vidx in g_new.edge_list():
            u = g_new.get_node_data(uidx)[0]
            v = g_new.get_node_data(vidx)[0]
            g_new_eidx_list.append((u, v))
        self.remove_edges_from(g_edge_list)
        self.add_edges_from(g_new_eidx_list)

    def get_isolates(self) -> list[int]:
        """Return a list of isolated nodes (nodes with no edges).

        See :meth:`BaseGraphState.get_isolates`.
        """
        # return list(rx.isolates(self.graph))  # will work with rustworkx>=0.14.0
        return [nnum for nnum, deg in self.degree() if deg == 0]
TW_EOF
mkdir -p graphix/graphsim
cat > graphix/graphsim/rxgraphviews.py <<'TW_EOF'
"""Node list class for RXGraphState."""

from __future__ import annotations

from typing import Any, Iterator


class NodeList:
    """Node list class for RXGraphState.

    In rustworkx, node data is stored in a tuple (node_num, node_data),
    and adding/removing nodes by node_num is not supported.
    This class defines a node list with node_num as key.
    """

    def __init__(
        self,
        node_nums: list[int] | None = None,
        node_datas: list[dict] | None = None,
        node_indices: list[int] | None = None,
    ):
        """Initialize a node list."""
        if node_indices is None:
            node_indices = []
        if node_datas is None:
            node_datas = []
        if node_nums is None:
            node_nums = []
        if not (len(node_nums) == len(node_datas) and len(node_nums) == len(node_indices)):
            raise ValueError("node_nums, node_datas and node_indices must have the same length")
        self.nodes = set(node_nums)
        self.num_to_data = {nnum: node_datas[nidx] for nidx, nnum in zip(node_indices, node_nums)}
        self.num_to_idx = {nnum: nidx for nidx, nnum in zip(node_indices, node_nums)}
        self.idx_to_num = {nidx: nnum for nidx, nnum in zip(node_indices, node_nums)}

    def __contains__(self, nnum: int) -> bool:
        """Return `True` if the node `nnum` belongs to the list, `False` otherwise."""
        return nnum in self.nodes

    def __getitem__(self, nnum: int) -> Any:
        """Return the data associated to node `nnum`."""
        return self.num_to_data[nnum]

    def __len__(self) -> int:
        """Return the number of nodes."""
        return len(self.nodes)

    def __iter__(self) -> Iterator[int]:
        """Return an iterator over nodes."""
        return iter(self.nodes)

    # TODO: This is not an evaluable __repr__. Define __str__ instead?
    def __repr__(self) -> str:
        """Return a string representation for the node list."""
        return "NodeList" + str(list(self.nodes))

    def get_node_index(self, nnum: int) -> int:
        """Return the index of the node `nnum`."""
        return self.num_to_idx[nnum]

    def add_node(self, nnum: int, ndata: dict, nidx: int) -> None:
        """Add a node to the list."""
        if nnum in self.num_to_data:
            raise ValueError(f"Node {nnum} already exists")
        self.nodes.add(nnum)
        self.num_to_data[nnum] = ndata
        self.num_to_idx[nnum] = nidx
        self.idx_to_num[nidx] = nnum

    def add_nodes_from(self, node_nums: list[int], node_datas: list[dict], node_indices: list[int]) -> None:
        """Add nodes to the list."""
        if not (len(node_nums) == len(node_datas) and len(node_nums) == len(node_indices)):
            raise ValueError("node_nums, node_datas and node_indices must have the same length")
        for nnum, ndata, nidx in zip(node_nums, node_datas, node_indices):
            if nnum in self.nodes:
                continue
            self.add_node(nnum, ndata, nidx)

    def remove_node(self, nnum: int) -> None:
        """Remove a node from the list."""
        if nnum not in self.num_to_data:
            raise ValueError(f"Node {nnum} does not exist")
        self.nodes.remove(nnum)
        del self.num_to_data[nnum]
        idx = self.num_to_idx.pop(nnum)
        del self.idx_to_num[idx]

    def remove_nodes_from(self, node_nums: list[int]) -> None:
        """Remove nodes from the list."""
        for nnum in node_nums:
            if nnum not in self.nodes:
                continue
            self.remove_node(nnum)


class EdgeList:
    """Edge list class for RXGraphState.

    In rustworkx, edge data is stored in a tuple (parent, child, edge_data),
    and adding/removing edges by (parent, child) is not supported.
    This class defines a edge list with (parent, child) as key.
    """

    def __init__(
        self,
        edge_nums: list[tuple[int, int]] | None = None,
        edge_datas: list[dict] | None = None,
        edge_indices: list[int] | None = None,
    ):
        """Initialize an edge list."""
        if edge_indices is None:
            edge_indices = []
        if edge_datas is None:
            edge_datas = []
        if edge_nums is None:
            edge_nums = []
        if not (len(edge_nums) == len(edge_datas) and len(edge_nums) == len(edge_indices)):
            raise ValueError("edge_nums, edge_datas and edge_indices must have the same length")
        self.edges = set(edge_nums)
        self.num_to_data = {enum: edge_datas[eidx] for eidx, enum in zip(edge_indices, edge_nums)}
        self.num_to_idx = {enum: eidx for eidx, enum in zip(edge_indices, edge_nums)}
        self.nnum_to_edges = {}
        for enum in edge_nums:
            if enum[0] not in self.nnum_to_edges:
                self.nnum_to_edges[enum[0]] = set()
            if enum[1] not in self.nnum_to_edges:
                self.nnum_to_edges[enum[1]] = set()
            self.nnum_to_edges[enum[0]].add(enum)
            self.nnum_to_edges[enum[1]].add(enum)

    def __contains__(self, enum: tuple[int, int]) -> bool:
        """Return `True` if the edge `enum` belongs to the list, `False` otherwise."""
        return enum in self.edges

    def __getitem__(self, enum: tuple[int, int]) -> Any:
        """Return the data associated to edge `enum`."""
        return self.num_to_data[enum]

    def __len__(self):
        """Return the number of edges."""
        return len(self.edges)

    def __iter__(self) -> Iterator[int]:
        """Return an iterator over edges."""
        return iter(self.edges)

    # TODO: This is not an evaluable __repr__. Define __str__ instead?
    def __repr__(self) -> str:
        """Return a string representation for the edge list."""
        return "EdgeList" + str(list(self.edges))

    def get_edge_index(self, enum: tuple[int, int]) -> int:
        """Return the index of the edge `enum`."""
        return self.num_to_idx[enum]

    def add_edge(self, enum: tuple[int, int], edata: dict, eidx: int) -> None:
        """Add an edge to the list."""
        if enum in self.num_to_data:
            raise ValueError(f"Edge {enum} already exists")
        self.edges.add(enum)
        self.num_to_data[enum] = edata
        self.num_to_idx[enum] = eidx
        if enum[0] not in self.nnum_to_edges:
            self.nnum_to_edges[enum[0]] = set()
        if enum[1] not in self.nnum_to_edges:
            self.nnum_to_edges[enum[1]] = set()
        self.nnum_to_edges[enum[0]].add(enum)
        self.nnum_to_edges[enum[1]].add(enum)

    def add_edges_from(self, edge_nums: list[tuple[int, int]], edge_datas: list[dict], edge_indices: list[int]) -> None:
        """Add edges to the list."""
        if not (len(edge_nums) == len(edge_datas) and len(edge_nums) == len(edge_indices)):
            raise ValueError("edge_nums, edge_datas and edge_indices must have the same length")
        for enum, edata, eidx in zip(edge_nums, edge_datas, edge_indices):
            if enum in self.edges:
                continue
            self.add_edge(enum, edata, eidx)

    def remove_edge(self, enum: tuple[int, int]) -> None:
        """Remove an edge from the list."""
        if enum not in self.num_to_data:
            raise ValueError(f"Edge {enum} does not exist")
        self.edges.remove(enum)
        del self.num_to_data[enum]
        del self.num_to_idx[enum]
        if enum[0] not in self.nnum_to_edges:
            self.nnum_to_edges[enum[0]] = set()
        if enum[1] not in self.nnum_to_edges:
            self.nnum_to_edges[enum[1]] = set()
        self.nnum_to_edges[enum[0]].remove(enum)
        self.nnum_to_edges[enum[1]].remove(enum)

    def remove_edges_from(self, edge_nums: list[tuple[int, int]]) -> None:
        """Remove edges from the list."""
        for enum in edge_nums:
            if enum not in self.edges:
                continue
            self.remove_edge(enum)

    def remove_edges_by_node(self, nnum: int):
        """Remove all edges connected to the node `nnum`."""
        if nnum in self.nnum_to_edges:
            for enum in self.nnum_to_edges[nnum]:
                self.edges.remove(enum)
                del self.num_to_data[enum]
                del self.num_to_idx[enum]
                if enum[0] == nnum:
                    self.nnum_to_edges[enum[1]].remove(enum)
                else:
                    self.nnum_to_edges[enum[0]].remove(enum)
TW_EOF
