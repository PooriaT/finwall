import type { Portfolio } from "../../api/types";
import { ActionableEmptyState } from "./ActionableEmptyState";
import { formatText } from "./format";

type WatchlistTableProps = {
  watchlist: NonNullable<Portfolio["watchlist"]>;
};

export function WatchlistTable({ watchlist }: WatchlistTableProps) {
  return (
    <section className="dashboard-section" aria-labelledby="watchlist-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2 id="watchlist-title">Tracked ideas</h2>
        </div>
      </div>
      {watchlist.length === 0 ? (
        <ActionableEmptyState
          title="No watchlist items yet"
          message="Add tickers you want to monitor without adding them as holdings."
          nextStep="Use watchlist entries for ideas you are tracking but have not added to the portfolio."
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((item) => (
                <tr key={item.ticker}>
                  <th scope="row">{item.ticker}</th>
                  <td>{formatText(item.note)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
