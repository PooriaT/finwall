import { ActionableEmptyState } from "./ActionableEmptyState";

export function EmptyState() {
  return (
    <div className="state-card empty-state">
      <ActionableEmptyState
        title="No local portfolio data yet"
        message="Finwall has no local portfolio state for this database yet. Add cash and at least one holding before dashboard valuation, allocation, and risk context can become useful."
        nextStep="The frontend is read-only for portfolio data today. Use the CLI until mutation screens exist; Finwall does not connect to brokers or execute orders."
        commandHint={
          "poetry run finwall --database finwall.db add-cash USD 1000\npoetry run finwall --database finwall.db add-holding AAPL 1 190 --sector Technology"
        }
      />
    </div>
  );
}
