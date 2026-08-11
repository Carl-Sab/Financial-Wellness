import { Link, useNavigate } from "react-router-dom";
import Button from "../Button";
import { useAuth } from "../../context/AuthContext";
import { useScrolled } from "../../hooks/useScrolled";
import "./Header.css";

function scrollToFeatures(event) {
  event.preventDefault();
  document.getElementById("features")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function Header() {
  const scrolled = useScrolled();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className={`header ${scrolled ? "header--scrolled" : ""}`}>
      <div className="header__inner">
        <Link to="/" className="header__logo">
          Financial&nbsp;Wellness
        </Link>

        <nav className="header__nav" aria-label="Primary">
          <a href="#features" className="header__link" onClick={scrollToFeatures}>
            Features
          </a>
          {user ? (
            <>
              <Link to="/home" className="header__user">
                {user.full_name}
              </Link>
              <Button variant="secondary" className="header__login" onClick={handleLogout}>
                Log out
              </Button>
            </>
          ) : (
            <Button as="link" to="/login" variant="secondary" className="header__login">
              Log in
            </Button>
          )}
        </nav>
      </div>
    </header>
  );
}
