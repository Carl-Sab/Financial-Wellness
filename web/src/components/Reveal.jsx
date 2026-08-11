import { useRevealOnScroll } from "../hooks/useRevealOnScroll";
import "./Reveal.css";

/**
 * Fades and rises its children into place once scrolled into view. No-ops
 * (renders already in place) under prefers-reduced-motion — see
 * useRevealOnScroll and the media query in Reveal.css.
 */
export default function Reveal({ as: Tag = "div", delay = 0, className = "", children, ...rest }) {
  const { ref, isVisible } = useRevealOnScroll();
  const classes = ["reveal", isVisible && "reveal--visible", className].filter(Boolean).join(" ");

  return (
    <Tag ref={ref} className={classes} style={{ "--reveal-delay": `${delay}ms` }} {...rest}>
      {children}
    </Tag>
  );
}
