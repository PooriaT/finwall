import type { Portfolio } from "../../api/types";
import { ActionableEmptyState } from "./ActionableEmptyState";
import { formatNumber } from "./format";

type CashTableProps = {
  cashBalances: NonNullable<Portfolio["cash_balances"]>;
};

export function CashTable({ cashBalances }: CashTableProps) {
  return (
    <section className="dashboard-section" aria-labelledby="cash-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Cash</p>
          <h2 id="cash-title">Cash balances</h2>
        </div>
      </div>
      {cashBalances.length === 0 ? (
        <ActionableEmptyState
          title="No cash balances yet"
          message="Add cash so Finwall can distinguish available cash from invested value."
          nextStep="Record at least one currency balance before using cash-vs-invested summaries."
          commandHint="poetry run finwall --database finwall.db add-cash USD 1000"
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Currency</th>
                <th scope="col">Amount</th>
              </tr>
            </thead>
            <tbody>
              {cashBalances.map((cash) => (
                <tr key={cash.currency}>
                  <th scope="row">{cash.currency}</th>
                  <td>{formatNumber(cash.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
