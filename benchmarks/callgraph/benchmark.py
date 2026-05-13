def _collect_entry_point_names(graph: dict) -> set[str]:
    entry_points = set()
    for ep in graph.get("entry_points", []):
        entry_points.add(_extract_entry_point_name(ep))
    return entry_points


def _add_connected_priority_nodes(
    edges: list[dict[str, str]], entry_points: set[str]
) -> set[str]:
    priority_nodes = set(entry_points)
    for edge in edges:
        if edge.get("from") in entry_points or edge.get("to") in entry_points:
            priority_nodes.add(edge.get("from"))
            priority_nodes.add(edge.get("to"))
    return priority_nodes


def _rank_nodes_by_degree(edges: list[dict[str, str]], max_nodes: int) -> list[str]:
    degree: dict[str, int] = {}
    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if src:
            degree[src] = degree.get(src, 0) + 1
        if dst:
            degree[dst] = degree.get(dst, 0) + 1

    if not degree:
        return []

    ranked = sorted(degree.items(), key=lambda item: item[1], reverse=True)
    return [node for node, _ in ranked[:max_nodes]]


def _sort_and_limit_priority_nodes(
    priority_nodes: set[str], max_nodes: int
) -> list[str]:
    return sorted(priority_nodes)[:max_nodes]


def _collect_priority_nodes(
    graph: dict, edges: list[dict[str, str]], max_nodes: int
) -> list[str]:
    entry_points = _collect_entry_point_names(graph)
    priority_nodes = _add_connected_priority_nodes(edges, entry_points)

    if not priority_nodes:
        ranked_nodes = _rank_nodes_by_degree(edges, max_nodes)
        if ranked_nodes:
            priority_nodes.update(ranked_nodes)
        else:
            return []

    return _sort_and_limit_priority_nodes(priority_nodes, max_nodes)
