"""兼容名：W1-21 的最小 EventEmitter 已由 TrajectoryRecorder（W1-24）取代。"""

from triwitness.telemetry.trajectory import TrajectoryRecorder

EventEmitter = TrajectoryRecorder

__all__ = ["EventEmitter", "TrajectoryRecorder"]
