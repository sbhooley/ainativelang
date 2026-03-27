# Extending Intelligence Programs with Cost Tracking

When writing `.lang` programs that use LLMs:

1. Import the cost tracking API:
   ```python
   from intelligence.monitor.cost_tracker import CostTracker
   from intelligence.monitor.budget_policy import BudgetPolicy
   ```

2. At the start of the program (each run), generate a `run_id` (UUID) and call `BudgetPolicy().check_and_enforce(run_id)`.

3. After obtaining `LLMResponse.usage`, call `CostTracker().add_cost(...)`.

4. Errors during LLM calls should still log cost if partial usage is available.

See `docs/MONITORING_OPERATIONS.md` for details.
