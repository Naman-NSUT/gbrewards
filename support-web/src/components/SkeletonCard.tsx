/**
 * Placeholder shaped like a WarrantyCard.
 *
 * It exists to hold the scroll position still, not to entertain: results append
 * below the search box, and a skeleton of roughly the right height means the
 * page does not jump under the customer's thumb when the answer arrives.
 */
export function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-line" style={{ width: '55%', height: '1.125rem' }} />
      <div className="skeleton-line" style={{ width: '80%' }} />
      <div className="skeleton-line" style={{ width: '70%' }} />
      <div className="skeleton-line" style={{ width: '45%' }} />
      <div className="skeleton-line" style={{ width: '85%', height: '3rem' }} />
    </div>
  );
}
