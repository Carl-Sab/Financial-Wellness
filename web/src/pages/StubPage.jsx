import { Link } from "react-router-dom";
import "./StubPage.css";

// Placeholder for /checkin, /statistics, /bank — real screens land later.
export default function StubPage({ title }) {
  return (
    <div className="stub">
      <p className="stub__eyebrow">Coming soon</p>
      <h1 className="stub__title">{title}</h1>
      <Link to="/home" className="stub__back">
        &larr; Back to home
      </Link>
    </div>
  );
}
