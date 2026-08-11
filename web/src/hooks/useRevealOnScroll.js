import { useEffect, useRef, useState } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Ref to attach to an element; isVisible flips true once the element has
 * scrolled into view — or scrolled past it entirely. Deliberately not
 * IntersectionObserver: a keyboard user can Tab straight past a section
 * with no focusable content of its own (this page's Features and How it
 * works cards have none), landing on a control further down and jumping
 * the viewport there in one step. That takes the element's intersection
 * ratio from 0 (below the viewport) directly to 0 (above it) without ever
 * crossing a nonzero threshold in between, so an IntersectionObserver
 * callback never fires and the section is stuck invisible forever.
 * Checking the bounding rect directly on scroll/resize/focus catches both
 * "scrolled into view" and "scrolled past" the same way.
 */
export function useRevealOnScroll() {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(prefersReducedMotion);

  useEffect(() => {
    const node = ref.current;
    if (prefersReducedMotion() || !node) return undefined;

    let rafId = null;

    const check = () => {
      rafId = null;
      // True once the element's top has crossed into (or past) the
      // viewport — covers "approaching from below", "currently in view",
      // and "already scrolled past" in one comparison.
      if (node.getBoundingClientRect().top < window.innerHeight - 60) {
        setIsVisible(true);
        cleanup();
      }
    };

    const schedule = () => {
      if (rafId === null) rafId = requestAnimationFrame(check);
    };

    function cleanup() {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("focusin", schedule);
      if (rafId !== null) cancelAnimationFrame(rafId);
    }

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("focusin", schedule);
    schedule(); // also covers content already in view on load

    return cleanup;
  }, []);

  return { ref, isVisible };
}
