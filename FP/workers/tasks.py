import random
import time

from celery import shared_task


@shared_task(name="workers.tasks.slow_add")
def slow_add(a: int, b: int, delay_s: float = 2.0) -> dict:
    time.sleep(float(delay_s))
    return {"a": a, "b": b, "sum": a + b, "delay_s": float(delay_s)}


@shared_task(
    bind=True,
    name="workers.tasks.flaky",
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def flaky(self, p_fail: float = 0.5) -> dict:
    p = float(p_fail)
    if random.random() < p:
        raise RuntimeError(f"Random failure {p}")
    return {"ok": True, "p_fail": p, "attempt": self.request.retries + 1}


@shared_task(name="workers.tasks.ping")
def ping() -> dict:
    return {"pong": True, "ts": time.time()}