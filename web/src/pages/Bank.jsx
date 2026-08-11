import { useState } from "react";
import { Link } from "react-router-dom";
import { useCardData } from "../hooks/useCardData";
import { apiFetch } from "../lib/api";
import { formatMoney } from "../lib/currency";
import { CATEGORIES } from "./checkinItems";
import "./Bank.css";

const PAGE_SIZE = 50;

const CATEGORY_LABELS = Object.fromEntries(CATEGORIES.map((c) => [c.code, c.label]));

async function fetchFirstPage() {
  const response = await apiFetch(`/api/v1/transactions?limit=${PAGE_SIZE}&offset=0`);
  if (!response.ok) throw new Error("Failed to load transactions");
  return response.json();
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function Bank() {
  const { status, data: firstPage, retry } = useCardData(fetchFirstPage);
  // Additional pages fetched via "Load more" — kept separate from the
  // useCardData cycle above, which only owns the first page's load/retry.
  const [morePages, setMorePages] = useState([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);

  const transactions = status === "success" ? [...firstPage, ...morePages.flat()] : [];
  const lastPage = morePages.length > 0 ? morePages[morePages.length - 1] : firstPage;
  const hasMore = status === "success" && lastPage != null && lastPage.length === PAGE_SIZE;

  async function loadMore() {
    setLoadingMore(true);
    setMoreError(false);
    try {
      const response = await apiFetch(
        `/api/v1/transactions?limit=${PAGE_SIZE}&offset=${transactions.length}`
      );
      if (!response.ok) throw new Error("Failed to load more transactions");
      const page = await response.json();
      setMorePages((prev) => [...prev, page]);
    } catch {
      setMoreError(true);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="bank-page">
      <div className="bank-page__topbar">
        <Link to="/home" className="bank-page__back">
          &larr; Home
        </Link>
      </div>

      <div className="bank-page__content">
        <h1 className="bank-page__title">Bank</h1>

        {status === "loading" && (
          <div className="bank-page__skeleton" aria-hidden="true">
            <span className="bank-page__skeleton-row" />
            <span className="bank-page__skeleton-row" />
            <span className="bank-page__skeleton-row" />
          </div>
        )}

        {status === "error" && (
          <div className="bank-page__error" role="alert">
            <p>Couldn&rsquo;t load your purchase history.</p>
            <button type="button" className="bank-page__retry" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        {status === "success" && transactions.length === 0 && (
          <p className="bank-page__empty">No purchases recorded yet.</p>
        )}

        {status === "success" && transactions.length > 0 && (
          <>
            <ul className="bank-page__list">
              {transactions.map((tx) => (
                <li key={tx.id} className="bank-page__row">
                  <div className="bank-page__row-main">
                    <span className="bank-page__row-category">
                      {CATEGORY_LABELS[tx.category_code] ?? tx.category_code}
                    </span>
                    {tx.merchant_name && (
                      <span className="bank-page__row-merchant">{tx.merchant_name}</span>
                    )}
                  </div>
                  <div className="bank-page__row-side">
                    <span className="bank-page__row-amount">
                      {formatMoney(tx.amount, tx.currency)}
                    </span>
                    <span className="bank-page__row-date">{formatDate(tx.occurred_at)}</span>
                  </div>
                </li>
              ))}
            </ul>

            {hasMore && (
              <button
                type="button"
                className="bank-page__load-more"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            )}

            {moreError && (
              <p className="bank-page__row-error" role="alert">
                Couldn&rsquo;t load more.{" "}
                <button type="button" className="bank-page__retry" onClick={loadMore}>
                  Try again
                </button>
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
