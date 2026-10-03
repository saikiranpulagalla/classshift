from __future__ import annotations

import logging
from dataclasses import dataclass

from ortools.graph.python import min_cost_flow

from .candidates import CandidateGraph, build_candidate_graph
from .domain import Dataset, ProposedAssignment, PublicStatus

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptimizeResult:
    status: PublicStatus
    assignments: tuple[ProposedAssignment, ...] | None = None
    move_count: int | None = None
    candidate_graph: CandidateGraph | None = None
    message: str = ""


def optimize_period(dataset: Dataset, outages, period_id: str) -> OptimizeResult:
    lessons = [lesson for lesson in dataset.lessons if lesson.period_id == period_id]
    graph = build_candidate_graph(dataset, outages, period_id)
    if not lessons:
        return OptimizeResult(PublicStatus.OPTIMAL, (), 0, graph)

    try:
        solver = min_cost_flow.SimpleMinCostFlow()
        source = 0
        lesson_offset = 1
        room_offset = lesson_offset + len(lessons)
        sink = room_offset + len(dataset.rooms)
        lesson_node = {lesson.id: lesson_offset + i for i, lesson in enumerate(lessons)}
        room_node = {room.id: room_offset + i for i, room in enumerate(dataset.rooms)}
        room_id_by_node = {node: room_id for room_id, node in room_node.items()}

        for lesson in lessons:
            solver.add_arc_with_capacity_and_unit_cost(source, lesson_node[lesson.id], 1, 0)
            for room_id in graph.eligible[lesson.id]:
                cost = 0 if room_id == lesson.original_room_id else 1
                solver.add_arc_with_capacity_and_unit_cost(
                    lesson_node[lesson.id], room_node[room_id], 1, cost
                )
        for room in dataset.rooms:
            solver.add_arc_with_capacity_and_unit_cost(room_node[room.id], sink, 1, 0)

        solver.set_node_supply(source, len(lessons))
        solver.set_node_supply(sink, -len(lessons))
        status = solver.solve()
        if status == solver.INFEASIBLE:
            return OptimizeResult(
                PublicStatus.INFEASIBLE,
                candidate_graph=graph,
                message="No complete assignment exists.",
            )
        if status != solver.OPTIMAL:
            LOGGER.error("OR-Tools returned unexpected status %r", status)
            return OptimizeResult(
                PublicStatus.SOLVER_ERROR,
                candidate_graph=graph,
                message="The optimization solver did not return a proven optimum.",
            )

        assignments: list[ProposedAssignment] = []
        lesson_id_by_node = {node: lesson_id for lesson_id, node in lesson_node.items()}
        lesson_by_id = {lesson.id: lesson for lesson in lessons}
        for arc in range(solver.num_arcs()):
            if solver.flow(arc) != 1:
                continue
            tail = solver.tail(arc)
            head = solver.head(arc)
            if tail in lesson_id_by_node and head in room_id_by_node:
                lesson_id = lesson_id_by_node[tail]
                assignments.append(
                    ProposedAssignment(
                        lesson_id=lesson_id,
                        period_id=lesson_by_id[lesson_id].period_id,
                        room_id=room_id_by_node[head],
                    )
                )

        if len(assignments) != len(lessons):
            return OptimizeResult(
                PublicStatus.SOLVER_ERROR,
                candidate_graph=graph,
                message="The optimization solver returned an incomplete assignment.",
            )

        moves = sum(
            assignment.room_id != lesson_by_id[assignment.lesson_id].original_room_id
            for assignment in assignments
            if assignment.lesson_id in lesson_by_id
        )
        return OptimizeResult(PublicStatus.OPTIMAL, tuple(assignments), moves, graph)
    except Exception:
        LOGGER.exception("OR-Tools optimization failed")
        # Public-facing optimizer errors are intentionally generic. Internal
        # details belong in server logs, not API payloads.
        return OptimizeResult(
            PublicStatus.SOLVER_ERROR,
            candidate_graph=graph,
            message="The optimization solver encountered an internal error.",
        )
