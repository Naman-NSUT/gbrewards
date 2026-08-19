import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <>
      <div className="page-head">
        <h1>Page not found</h1>
        <p>
          That address does not exist on the GoodBed warranty site. If you followed a link from an
          SMS, open the full link — some phones cut long links in half.
        </p>
      </div>
      <div className="card">
        <div className="link-row" style={{ marginTop: 0 }}>
          <Link className="btn btn--primary" to="/">
            Check a warranty
          </Link>
          <Link className="btn btn--secondary" to="/register">
            Register a warranty
          </Link>
        </div>
      </div>
    </>
  );
}
