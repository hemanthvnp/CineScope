"""
Execution engine — resolves and runs the ExecutionPlan as a DAG.

Algorithm:
  1. Find all nodes whose dependencies are already complete → "ready set"
  2. Fire the entire ready set concurrently via asyncio.gather()
  3. Collect results, mark nodes complete (or failed)
  4. Repeat until no nodes remain pending

Each node call:
  • checks the tool-level cache first
  • wraps the tool fn in a circuit breaker
  • enforces a per-tool timeout
  • injects resolved dependency results into params under `_dep_<node_id>` keys
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

from cache.semantic_cache import cache_get, cache_set, make_tool_key
from models.intent import ExecutionPlan, PlanNode
from orchestrator.circuit_breaker import CircuitOpenError, get_breaker
from tools.registry import TOOL_REGISTRY


class ExecutionEngine:

    async def run(self, plan: ExecutionPlan) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        completed: set[str] = set()
        failed: set[str] = set()
        services_invoked: List[str] = []

        pending = list(plan.nodes)

        while pending:
            ready = self._ready_nodes(pending, completed, failed, plan)

            if not ready:
                # No progress — remaining nodes have failed/unresolvable deps
                break

            for node in ready:
                pending.remove(node)

            batch = await asyncio.gather(
                *[self._run_node(node, results) for node in ready],
                return_exceptions=True,
            )

            for node, result in zip(ready, batch):
                services_invoked.append(node.tool)
                if isinstance(result, Exception):
                    print(f"[engine] '{node.id}' ({node.tool}) failed: {result}")
                    failed.add(node.id)
                    results[node.id] = None
                else:
                    completed.add(node.id)
                    results[node.id] = result

        # Deduplicate while preserving insertion order
        seen: dict[str, bool] = {}
        for s in services_invoked:
            seen[s] = True
        results["_services_invoked"] = list(seen.keys())
        return results

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ready_nodes(
        self,
        pending: List[PlanNode],
        completed: set[str],
        failed: set[str],
        plan: ExecutionPlan,
    ) -> List[PlanNode]:
        ready = []
        for node in pending:
            # All deps must be completed, or failed+optional
            deps_ok = all(
                dep in completed
                or (dep in failed and self._is_optional(dep, plan))
                for dep in node.dependencies
            )
            # Don't start if any hard dependency failed
            hard_fail = any(
                dep in failed and not self._is_optional(dep, plan)
                for dep in node.dependencies
            )
            if deps_ok and not hard_fail:
                ready.append(node)
        return ready

    def _is_optional(self, node_id: str, plan: ExecutionPlan) -> bool:
        for node in plan.nodes:
            if node.id == node_id:
                return node.optional
        return False

    async def _run_node(self, node: PlanNode, context: Dict[str, Any]) -> Any:
        cfg = TOOL_REGISTRY.get(node.tool)
        if not cfg:
            raise ValueError(f"Unknown tool: '{node.tool}'")

        # Build params — inject dependency results
        params = dict(node.params)
        for dep_id in node.dependencies:
            if context.get(dep_id) is not None:
                params[f"_dep_{dep_id}"] = context[dep_id]

        # Tool-level cache check
        cache_key = make_tool_key(node.tool, params)
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        timeout_s = cfg.get("timeout_ms", 5_000) / 1_000
        cb = get_breaker(cfg.get("circuit_breaker", node.tool))

        t0 = time.monotonic()
        async with cb:
            try:
                result = await asyncio.wait_for(
                    cfg["fn"](params),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError:
                elapsed = round((time.monotonic() - t0) * 1000)
                raise TimeoutError(
                    f"Tool '{node.tool}' timed out after {elapsed}ms"
                )

        # Write-through cache
        ttl = cfg.get("cache_ttl", 300)
        await cache_set(cache_key, result, ttl=ttl)
        return result
