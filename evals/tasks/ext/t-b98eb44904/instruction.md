[Bug]: `rustworkx` fails to handle non-contiguous node numbering
The following code raises `KeyError` in `rxgraphviews.get_node_index` when `use_rustworkx` is `True`:
```python
    @pytest.mark.parametrize("use_rustworkx", [False, True])
    def test_pauli_non_contiguous(self, use_rustworkx) -> None:
        pattern = Pattern(input_nodes=[0])
        pattern.extend([
            N(node=2, state=PlanarState(plane=Plane.XY, angle=0.0)),
            E(nodes=(0, 2)),
            M(node=0, plane=Plane.XY, angle=0.0, s_domain=set(), t_domain=set())
        ])
        pattern.perform_pauli_measurements(use_rustworkx=use_rustworkx)
```

The bug seems to be between `RXGraphState.neighbors`, `RXGraphState.subgraphs` and `RXGraphState.local_complement`: the indexes returned by `neighbors` are in the rustworkx numbering, whereas `local_complement` calls `subgraphs` on these nodes, which expects them to be in the graphix numbering.

A fix could be to add a `idx_to_num` mapping in `rxgraphviews` and convert neighbors in the graphix numbering.

Related issues: #206 (problem with `rxgraphviews`).
