import type { Portfolio } from "../../api/types";
import { ActionableEmptyState } from "./ActionableEmptyState";
import { formatLabel, formatNumber } from "./format";

type ActiveOrdersTableProps = {
  activeOrders: NonNullable<Portfolio["active_orders"]>;
};

export function ActiveOrdersTable({ activeOrders }: ActiveOrdersTableProps) {
  return (
    <section className="dashboard-section" aria-labelledby="orders-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Active Orders</p>
          <h2 id="orders-title">Open order plan</h2>
        </div>
      </div>
      {activeOrders.length === 0 ? (
        <ActionableEmptyState
          title="No planned orders recorded"
          message="Orders in Finwall are local planning records only; they are not broker orders."
          nextStep="Use this section only when you want saved buy or sell plans to appear beside your holdings context."
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Side</th>
                <th scope="col">Order type</th>
                <th scope="col">Shares</th>
                <th scope="col">Limit price</th>
                <th scope="col">Stop price</th>
              </tr>
            </thead>
            <tbody>
              {activeOrders.map((order) => (
                <tr key={`${order.ticker}-${order.side}-${order.order_type}`}>
                  <th scope="row">{order.ticker}</th>
                  <td>{formatLabel(order.side)}</td>
                  <td>{formatLabel(order.order_type)}</td>
                  <td>{formatNumber(order.share_count)}</td>
                  <td>{formatNumber(order.limit_price)}</td>
                  <td>{formatNumber(order.stop_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
