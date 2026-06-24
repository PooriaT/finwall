import type { Portfolio } from "../../api/types";
import { ActionableEmptyState } from "./ActionableEmptyState";
import { formatNumber, formatText } from "./format";

type HoldingsTableProps = {
  holdings: NonNullable<Portfolio["holdings"]>;
};

export function HoldingsTable({ holdings }: HoldingsTableProps) {
  return (
    <section className="dashboard-section" aria-labelledby="holdings-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Holdings</p>
          <h2 id="holdings-title">Current holdings</h2>
        </div>
      </div>
      {holdings.length === 0 ? (
        <ActionableEmptyState
          title="No holdings yet"
          message="Add a holding through the CLI so Finwall can calculate allocation, valuation, and risk context."
          nextStep="Start with one small example holding, then check live-data status before relying on valuation views."
          commandHint="poetry run finwall --database finwall.db add-holding AAPL 1 190 --sector Technology"
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Shares</th>
                <th scope="col">Average purchase price</th>
                <th scope="col">Sector</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((holding) => (
                <tr key={holding.ticker}>
                  <th scope="row">{holding.ticker}</th>
                  <td>{formatNumber(holding.share_count)}</td>
                  <td>{formatNumber(holding.average_purchase_price)}</td>
                  <td>{formatText(holding.sector)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
