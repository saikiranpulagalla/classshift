from __future__ import annotations

from dataclasses import dataclass

from ortools.graph.python import min_cost_flow

from .candidates import CandidateGraph, build_candidate_graph
from .domain import Dataset, PublicStatus


@dataclass(frozen=True)
class OptimizeResult:
    status: PublicStatus
    assignments: dict[str, str] | None = None
    move_count: int | None = None
    candidate_graph: CandidateGraph | None = None
    message: str = ""


def optimize_period(dataset: Dataset, outages, period_id: str) -> OptimizeResult:
    lessons = [l for l in dataset.lessons if l.period_id == period_id]
    if not lessons:
        return OptimizeResult(PublicStatus.OPTIMAL, {}, 0, build_candidate_graph(dataset, outages, period_id))

    graph = build_candidate_graph(dataset, outages, period_id)
    try:
        solver = min_cost_flow.SimpleMinCostFlow()
        source = 0
        lesson_offset = 1
        room_offset = lesson_offset + len(lessons)
        sink = room_offset + len(dataset.rooms)
        lesson_node = {lesson.id: lesson_offset + i for i, lesson in enumerate(lessons)}
        room_node = {room.id: room_offset + i for i, room in enumerate(dataset.rooms)}
        room_id_by_node = {node: rid for rid, node in room_node.items()}

        for lesson in lessons:
            solver.add_arc_with_capacity_and_unit_cost(source, lesson_node[lesson.id], 1, 0)
            for rid in graph.eligible[lesson.id]:
                cost = 0 if rid == lesson.original_room_id else 1
                solver.add_arc_with_capacity_and_unit_cost(lesson_node[lesson.id], room_node[rid], 1, cost)
        for room in dataset.rooms:
            solver.add_arc_with_capacity_and_unit_cost(room_node[room.id], sink, 1, 0)

        solver.set_node_supply(source, len(lessons))
        solver.set_node_supply(sink, -len(lessons))
        status = solver.solve()
        if status == solver.INFEASIBLE:
            return OptimizeResult(PublicStatus.INFEASIBLE, candidate_graph=graph, message="No complete assignment exists.")
        if status != solver.OPTIMAL:
            return OptimizeResult(PublicStatus.SOLVER_ERROR, candidate_graph=graph, message=f"OR-Tools returned status {status}.")

        assignments: dict[str, str] = {}
        lesson_id_by_node = {node: lid for lid, node in lesson_node.items()}
        for arc in range(solver.num_arcs()):
            if solver.flow(arc) != 1:
                continue
            tail = solver.tail(arc)
            head = solver.head(arc)
            if tail in lesson_id_by_node and head in room_id_by_node:
                assignments[lesson_id_by_node[tail]] = room_id_by_node[head]
        if len(assignments) != len(lessons):
            return OptimizeResult(PublicStatus.SOLVER_ERROR, candidate_graph=graph, message="Solver returned an incomplete assignment.")
        moves = sum(assignments[l.id] != l.original_room_id for l in lessons)
        return OptimizeResult(PublicStatus.OPTIMAL, assignments, moves, graph)
    except Exception as exc:
        return OptimizeResult(PublicStatus.SOLVER_ERROR, candidate_graph=graph, message=f"Solver exception: {type(exc).__name__}")
