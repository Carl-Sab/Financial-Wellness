import Button from "../Button";
import { buildEcgPath } from "./ecgPath";
import "./Hero.css";

const ECG_PATH = buildEcgPath({ width: 640, height: 64, cycles: 3 });

function scrollToFeatures(event) {
  event.preventDefault();
  document.getElementById("features")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function Hero() {
  return (
    <section className="hero">
      <div className="hero__inner">
        <div className="hero__copy">
          <h1 className="hero__title">See how you feel before you spend.</h1>
          <p className="hero__subhead">
            A quick check-in reads your heart rate and your mood, then shows you how much more
            you spend when you&rsquo;re stressed than when you&rsquo;re calm.
          </p>

          <div className="hero__actions">
            <Button as="link" to="/signup" variant="primary">
              Get started
            </Button>
            <Button as="a" href="#features" variant="secondary" onClick={scrollToFeatures}>
              See how it works
            </Button>
          </div>

          <div className="hero__ecg" aria-hidden="true">
            <svg viewBox="0 0 640 64" preserveAspectRatio="none" className="hero__ecg-svg">
              <path d={ECG_PATH} pathLength="1" className="hero__ecg-path" />
            </svg>
          </div>
        </div>

        <div className="hero__visual">
          <div className="hero__photo hero__photo--primary">
            {/* TODO: swap for a real photo — a wrist wearing a smartwatch, mid check-in */}
            <img
              src="https://images.unsplash.com/photo-1544117519-31a4b719223d?q=80&w=900&auto=format&fit=crop"
              alt=""
              loading="eager"
            />
          </div>
          <div className="hero__photo hero__photo--accent-a">
            {/* TODO: swap for a real photo — someone browsing in a shop */}
            <img
              src="https://images.unsplash.com/photo-1441986300917-64674bd600d8?q=80&w=500&auto=format&fit=crop"
              alt=""
              loading="lazy"
            />
          </div>
          <div className="hero__photo hero__photo--accent-b">
            {/* TODO: swap for a real photo — a calm moment at home */}
            <img
              src="https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?q=80&w=500&auto=format&fit=crop"
              alt=""
              loading="lazy"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
