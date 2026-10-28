"""Minimal Prometheus metrics, in the standard text exposition format.

Written by hand (no extra dependency) so the demo has a smaller attack surface.
"""

import threading

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple, int] = {}
        self._hist: dict[tuple, list] = {}  # (method, route) -> [bucket counts..., sum, count]

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            key = (method, route, str(status))
            self._requests[key] = self._requests.get(key, 0) + 1
            hkey = (method, route)
            h = self._hist.setdefault(hkey, [0] * len(BUCKETS) + [0.0, 0])
            for i, bound in enumerate(BUCKETS):
                if seconds <= bound:
                    h[i] += 1
            h[-2] += seconds
            h[-1] += 1

    def render(self, version: str, task_count: int) -> str:
        lines = [
            "# HELP app_info Application version.",
            "# TYPE app_info gauge",
            f'app_info{{version="{_escape(version)}"}} 1',
            "# HELP tasks_total Tasks stored in the database.",
            "# TYPE tasks_total gauge",
            f"tasks_total {task_count}",
            "# HELP http_requests_total HTTP requests by method, route and status.",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status), n in sorted(self._requests.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",route="{_escape(route)}",status="{status}"}} {n}'
                )
            lines += [
                "# HELP http_request_duration_seconds Request latency.",
                "# TYPE http_request_duration_seconds histogram",
            ]
            for (method, route), h in sorted(self._hist.items()):
                labels = f'method="{method}",route="{_escape(route)}"'
                for i, bound in enumerate(BUCKETS):
                    lines.append(f'http_request_duration_seconds_bucket{{{labels},le="{bound}"}} {h[i]}')
                lines.append(f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {h[-1]}')
                lines.append(f"http_request_duration_seconds_sum{{{labels}}} {h[-2]:.6f}")
                lines.append(f"http_request_duration_seconds_count{{{labels}}} {h[-1]}")
        return "\n".join(lines) + "\n"
