import time
import uuid
import threading
import logging
from typing import Optional, List, Dict, Any

try:
    from app.core.config import settings
except ImportError:
    settings = None

logger = logging.getLogger(__name__)


class QueueTicket:
    """
    Represents an individual request waiting in the virtual queue.
    """
    def __init__(self, ticket_id: str, position: int):
        self.ticket_id: str = ticket_id
        self.position: int = position
        self.created_at: float = time.time()
        self.ready_event: threading.Event = threading.Event()
        self.acquired: bool = False
        self.cancelled: bool = False

    def wake(self) -> None:
        """Signals the waiting thread that a slot may be available."""
        self.ready_event.set()

    def wait(self, timeout: float = 1.0) -> bool:
        """
        Blocks until woken or timeout expires. Clears the event after waking.
        """
        signaled = self.ready_event.wait(timeout=timeout)
        if signaled:
            self.ready_event.clear()
        return signaled


class VirtualQueueManager:
    """
    Thread-safe FIFO Virtual Queue Manager for managing concurrent stream traffic spikes.
    When the maximum concurrent active streaming slots (e.g. 150) are occupied,
    new requests enter this virtual queue up to QUEUE_CAPACITY, keeping the SSE connection
    alive with keepalive heartbeats and position notifications.
    """
    def __init__(self):
        self._lock: threading.Lock = threading.Lock()
        self._queue: List[QueueTicket] = []
        self._capacity_override: Optional[int] = None
        self._max_wait_override: Optional[float] = None

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def get_capacity(self) -> int:
        if self._capacity_override is not None:
            return self._capacity_override
        if settings and hasattr(settings, "QUEUE_CAPACITY"):
            return int(settings.QUEUE_CAPACITY)
        return 100

    def set_capacity(self, capacity: int) -> None:
        with self._lock:
            self._capacity_override = capacity

    def get_max_wait_seconds(self) -> float:
        if self._max_wait_override is not None:
            return self._max_wait_override
        if settings and hasattr(settings, "QUEUE_MAX_WAIT_SECONDS"):
            return float(settings.QUEUE_MAX_WAIT_SECONDS)
        return 15.0

    def set_max_wait_seconds(self, seconds: float) -> None:
        with self._lock:
            self._max_wait_override = seconds

    def get_queue_length(self) -> int:
        with self._lock:
            return len(self._queue)

    def has_waiters(self) -> bool:
        with self._lock:
            return len(self._queue) > 0

    def has_waiters_locked(self) -> bool:
        """Check without acquiring the lock (caller must hold self._lock)."""
        return len(self._queue) > 0

    def is_full(self) -> bool:
        with self._lock:
            return len(self._queue) >= self.get_capacity()

    def enqueue(self) -> Optional[QueueTicket]:
        """
        Attempts to enqueue a waiting request.
        Returns a QueueTicket if within capacity, or None if full / capacity is 0.
        """
        with self._lock:
            capacity = self.get_capacity()
            if capacity <= 0 or len(self._queue) >= capacity:
                logger.warning(
                    f"[VirtualQueue] Queue rejected: current length {len(self._queue)} >= capacity {capacity}"
                )
                return None

            ticket_id = f"ticket_{uuid.uuid4().hex[:8]}"
            position = len(self._queue) + 1
            ticket = QueueTicket(ticket_id=ticket_id, position=position)
            self._queue.append(ticket)
            logger.info(f"[VirtualQueue] Enqueued {ticket_id} at position #{position}")
            return ticket

    def try_claim_permit(self, ticket: QueueTicket, sem: threading.Semaphore) -> bool:
        """
        Attempts to claim an available permit from the semaphore for the given ticket.
        Only the head of the queue (ticket at index 0) is eligible to claim a permit,
        ensuring strict FIFO ordering and preventing slot race conditions.
        """
        with self._lock:
            if ticket.acquired:
                return True
            if not self._queue:
                return False
            if self._queue[0] is not ticket:
                return False

            acquired = sem.acquire(blocking=False)
            if acquired:
                ticket.acquired = True
                self._queue.pop(0)
                self._update_positions_locked()
                if self._queue:
                    self._queue[0].wake()
                logger.info(f"[VirtualQueue] Ticket {ticket.ticket_id} acquired slot from semaphore")
                return True
            return False

    def remove_ticket(self, ticket: QueueTicket) -> None:
        """
        Removes a ticket from the queue (e.g. on client disconnect or timeout).
        Recalculates positions and notifies the new head ticket if necessary.
        """
        with self._lock:
            was_head = (len(self._queue) > 0 and self._queue[0] is ticket)
            if ticket in self._queue:
                self._queue.remove(ticket)
                self._update_positions_locked()
                logger.info(f"[VirtualQueue] Removed ticket {ticket.ticket_id} (queue length: {len(self._queue)})")
            if not ticket.acquired:
                ticket.cancelled = True

            if was_head and len(self._queue) > 0:
                self._queue[0].wake()

    def notify_available(self) -> None:
        """
        Notifies waiting tickets that an active streaming slot was released.
        Wakes the ticket at the head of the queue.
        """
        with self._lock:
            if self._queue:
                self._queue[0].wake()

    def reset(self) -> None:
        """
        Clears all queue state and wakes any waiting tickets with cancellation.
        Primarily used for testing and baseline resets.
        """
        with self._lock:
            for ticket in self._queue:
                ticket.cancelled = True
                ticket.wake()
            self._queue.clear()
            self._capacity_override = None
            self._max_wait_override = None

    def _update_positions_locked(self) -> None:
        """Recalculates 1-indexed position for all tickets currently in queue."""
        for idx, t in enumerate(self._queue):
            t.position = idx + 1


# Global Singleton Instance
virtual_queue = VirtualQueueManager()
