"""LogFlowParser - Data flow analysis from logs with trace_id grouping and LLM compression."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class LogFlowParser:
    """Parser for log data flow analysis.
    
    Groups logs by trace_id, builds service interaction graphs,
    and compresses flows to LLM-friendly formats.
    """
    
    def __init__(self):
        self.grouped_logs: dict[str, list[dict[str, Any]]] = {}
        self.flow_graphs: dict[str, dict[str, Any]] = {}
    
    def parse_logs(self, logs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Parse logs and build data flow representation.
        
        Args:
            logs: List of log entries containing at least trace_id and service_name
            
        Returns:
            Dictionary mapping trace_id to sorted list of log entries
        """
        self.grouped_logs = self.group_by_trace_id(logs)
        self.flow_graphs = self._build_flow_graphs(self.grouped_logs)
        return self.grouped_logs
    
    def group_by_trace_id(self, logs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Group logs by trace_id and sort by timestamp.
        
        Args:
            logs: List of log entries
            
        Returns:
            Grouped logs sorted chronologically within each trace
        """
        grouped = defaultdict(list)
        for log in logs:
            trace_id = log.get('trace_id')
            if trace_id:
                grouped[trace_id].append(log)
        
        # Sort by timestamp within each trace
        for trace_id in grouped:
            grouped[trace_id].sort(key=lambda x: x.get('timestamp', 0))
        
        return dict(grouped)
    
    def _build_flow_graphs(self, grouped_logs: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
        """Build directed flow graphs for each trace.
        
        Args:
            grouped_logs: Logs grouped by trace_id
            
        Returns:
            Graph representation with nodes (services) and edges (calls)
        """
        graphs = {}
        for trace_id, logs in grouped_logs.items():
            nodes = set()
            edges = []
            
            for i, log in enumerate(logs):
                service = log.get('service_name') or log.get('service', 'unknown')
                nodes.add(service)
                
                # Create sequential edges based on log order
                if i < len(logs) - 1:
                    next_log = logs[i + 1]
                    next_service = next_log.get('service_name') or next_log.get('service', 'unknown')
                    if service != next_service:  # Only add edge if different services
                        edges.append({
                            'source': service,
                            'target': next_service,
                            'timestamp': log.get('timestamp'),
                            'index': i
                        })
            
            # Calculate duration
            start_time = logs[0].get('timestamp') if logs else None
            end_time = logs[-1].get('timestamp') if logs else None
            duration = (end_time - start_time) if start_time and end_time else None
            
            graphs[trace_id] = {
                'nodes': sorted(list(nodes)),
                'edges': edges,
                'log_count': len(logs),
                'start_time': start_time,
                'end_time': end_time,
                'duration_ms': duration
            }
        
        return graphs
    
    def compress_to_llm_format(self, trace_id: str | None = None) -> str:
        """Compress flow graph to compact LLM-friendly string format.
        
        Format: [trace_id]:ServiceA->ServiceB->ServiceC(logs:N,dur:Xms)
        
        Args:
            trace_id: Specific trace to compress, or None for all traces
            
        Returns:
            Compressed string representation
        """
        if not self.flow_graphs:
            return "{}"
        
        if trace_id:
            if trace_id not in self.flow_graphs:
                return "{}"
            return self._compress_single_trace(trace_id, self.flow_graphs[trace_id])
        
        # Compress all traces
        results = []
        for tid, graph in sorted(self.flow_graphs.items()):
            compressed = self._compress_single_trace(tid, graph)
            results.append(compressed)
        return "\n".join(results)
    
    def _compress_single_trace(self, trace_id: str, graph: dict[str, Any]) -> str:
        """Compress single trace to compact format."""
        if not graph['edges']:
            nodes = graph['nodes']
            node_str = nodes[0] if nodes else 'empty'
            return f"[{trace_id}]:{node_str}(logs:{graph['log_count']})"
        
        # Build path: A->B->C
        path = [graph['edges'][0]['source']]
        for edge in graph['edges']:
            path.append(edge['target'])
        
        # Remove consecutive duplicates while preserving order
        compact_path = [path[0]]
        for node in path[1:]:
            if node != compact_path[-1]:
                compact_path.append(node)
        
        path_str = "->".join(compact_path)
        
        # Build metadata
        meta_parts = [f"logs:{graph['log_count']}"]
        if graph['duration_ms'] is not None:
            meta_parts.append(f"dur:{graph['duration_ms']}ms")
        
        return f"[{trace_id}]:{path_str}({','.join(meta_parts)})"
    
    def get_trace_statistics(self, trace_id: str) -> dict[str, Any] | None:
        """Get statistics for a specific trace."""
        if trace_id not in self.flow_graphs:
            return None
        graph = self.flow_graphs[trace_id]
        return {
            'trace_id': trace_id,
            'service_count': len(graph['nodes']),
            'log_count': graph['log_count'],
            'duration_ms': graph['duration_ms'],
            'services': graph['nodes']
        }
    
    def get_global_statistics(self) -> dict[str, Any]:
        """Get global statistics across all traces."""
        if not self.grouped_logs:
            return {
                'total_traces': 0,
                'total_logs': 0,
                'avg_logs_per_trace': 0.0,
                'unique_services': []
            }
        
        total_traces = len(self.grouped_logs)
        total_logs = sum(len(logs) for logs in self.grouped_logs.values())
        
        all_services = set()
        for logs in self.grouped_logs.values():
            for log in logs:
                service = log.get('service_name') or log.get('service', 'unknown')
                all_services.add(service)
        
        return {
            'total_traces': total_traces,
            'total_logs': total_logs,
            'avg_logs_per_trace': total_logs / total_traces if total_traces > 0 else 0.0,
            'unique_services': sorted(list(all_services))
        }
