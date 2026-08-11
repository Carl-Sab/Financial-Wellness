import { Link } from "react-router-dom";
import "./Button.css";

/**
 * Shared button styling for the three variants used across the landing
 * page: primary (lime, on white/mist), secondary (outline, on white/mist),
 * dark (ink fill, for use on the lime join band where a lime button would
 * have no contrast).
 */
export default function Button({
  as = "button",
  to,
  href,
  variant = "primary",
  className = "",
  children,
  ...rest
}) {
  const classes = ["btn", `btn--${variant}`, className].filter(Boolean).join(" ");

  if (as === "link") {
    return (
      <Link to={to} className={classes} {...rest}>
        {children}
      </Link>
    );
  }

  if (as === "a") {
    return (
      <a href={href} className={classes} {...rest}>
        {children}
      </a>
    );
  }

  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}
