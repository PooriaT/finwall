import type { Portfolio } from "../../api/types";
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
        <p className="table-empty">No cash balances available.</p>
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
