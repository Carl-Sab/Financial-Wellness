import { Link } from "react-router-dom";
import "./Footer.css";

function scrollToFeatures(event) {
  event.preventDefault();
  document.getElementById("features")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <span className="footer__logo">Financial&nbsp;Wellness</span>

        <nav className="footer__nav" aria-label="Footer">
          <a href="#features" onClick={scrollToFeatures}>
            Features
          </a>
          <Link to="/login">Log in</Link>
        </nav>

        <p className="footer__meta">&copy; {new Date().getFullYear()} Financial Wellness</p>
      </div>
    </footer>
  );
}
