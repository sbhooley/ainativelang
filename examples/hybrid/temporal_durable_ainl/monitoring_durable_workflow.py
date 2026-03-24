"""
Temporal workflow for emitted AINL graph (monitoring_durable).

Requires: pip install temporalio
"""

from __future__ import annotations

from datetime import timedelta

try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy
except ImportError as e:  # pragma: no cover
    raise RuntimeError("Install temporalio: pip install temporalio") from e


# Import activities from the sibling module (same directory on worker PYTHONPATH).
with workflow.unsafe.imports_passed_through():
    import monitoring_durable_activities as _ainl_activities


@workflow.defn
class AinlMonitoringDurableWorkflow:
    @workflow.run
    async def run(self, input_data: dict) -> dict:
        """
        Customize: add signals/queries, child workflows, or multiple execute_activity
        steps. Adjust start_to_close_timeout and RetryPolicy (maximum_attempts,
        backoff_coefficient, non_retryable_error_types) per your SLOs.
        """
        return await workflow.execute_activity(
            _ainl_activities.run_ainl_core_activity,
            input_data,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
