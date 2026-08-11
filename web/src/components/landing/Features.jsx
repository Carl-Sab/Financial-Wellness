import Reveal from "../Reveal";
import "./Features.css";

const FEATURES = [
  {
    title: "Track your physical state",
    body: "Log a quick reading before you buy. We compare it to your own normal, not anyone else's.",
    icon: <path d="M2 12h4l2-6 4 12 3-9 2 3h5" />,
  },
  {
    title: "See spending by mood",
    body: "Every purchase gets tagged with how you felt at the time. Patterns show up on their own.",
    icon: <path d="M6 20V10M12 20V4M18 20V14" />,
  },
  {
    title: "Budgets that account for how you feel",
    body: "Set limits that flex with your state, not just a flat number every month.",
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      </>
    ),
  },
  {
    title: "A nudge before you overspend",
    body: "A short heads-up when a purchase looks like it's happening at the wrong moment.",
    icon: (
      <>
        <path d="M6 8a6 6 0 0 1 12 0c0 4 1.5 5.5 2 6H4c.5-.5 2-2 2-6Z" />
        <path d="M10 19a2 2 0 0 0 4 0" />
      </>
    ),
  },
];

export default function Features() {
  return (
    <section id="features" className="features">
      <div className="features__inner">
        <Reveal className="features__intro">
          <h2 className="features__heading">What you get</h2>
        </Reveal>

        <div className="features__grid">
          {FEATURES.map((feature, index) => (
            <Reveal as="article" key={feature.title} className="feature-card" delay={index * 80}>
              <span className="feature-card__icon" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {feature.icon}
                </svg>
              </span>
              <h3 className="feature-card__title">{feature.title}</h3>
              <p className="feature-card__body">{feature.body}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
