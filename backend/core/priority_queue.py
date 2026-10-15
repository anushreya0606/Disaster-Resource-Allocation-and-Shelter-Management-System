from dataclasses import dataclass, field
import heapq


@dataclass(order=True)
class PriorityEvacuee:
    """
    Represents an evacuee waiting for shelter allocation.

    Higher priority_score means higher priority.
    Since heapq is a min-heap, we store the negative score.
    """

    sort_index: int = field(init=False, repr=False)

    priority_score: int
    evacuee_id: int

    def __post_init__(self):
        self.sort_index = -self.priority_score


class PriorityQueue:
    """
    Priority queue for processing evacuees.

    Evacuees with higher priority scores are processed first.
    """

    def __init__(self):
        self._queue = []

    def push(
        self,
        evacuee_id: int,
        priority_score: int
    ) -> None:
        """
        Add an evacuee to the priority queue.
        """

        evacuee = PriorityEvacuee(
            priority_score=priority_score,
            evacuee_id=evacuee_id
        )

        heapq.heappush(self._queue, evacuee)

    def pop(self) -> PriorityEvacuee | None:
        """
        Remove and return the highest-priority evacuee.
        """

        if not self._queue:
            return None

        return heapq.heappop(self._queue)

    def peek(self) -> PriorityEvacuee | None:
        """
        View the highest-priority evacuee without removing them.
        """

        if not self._queue:
            return None

        return self._queue[0]

    def is_empty(self) -> bool:
        """
        Check whether the queue is empty.
        """

        return len(self._queue) == 0

    def size(self) -> int:
        """
        Return the number of evacuees waiting.
        """

        return len(self._queue)