import Reveal from "../Reveal";
import "./HowItWorks.css";

const STEPS = [
  {
    number: "01",
    title: "Check in before you buy",
    body: "A few seconds: heart rate, mood, done.",
  },
  {
    number: "02",
    title: "The app learns your normal",
    body: "Built from your own check-ins, not anyone else's average.",
  },
  {
    number: "03",
    title: "See the patterns",
    body: "How your spending changes with how you feel, laid out clearly.",
  },
];

export default function HowItWorks() {
  return (
    <section className="how">
      <div className="how__inner">
        <Reveal className="how__intro">
          <h2 className="how__heading">How it works</h2>
        </Reveal>

        <ol className="how__steps">
          {STEPS.map((step, index) => (
            <Reveal as="li" key={step.number} className="how-step" delay={index * 80}>
              <div className="how-step__eyebrow">
                <span className="how-step__marker" aria-hidden="true" />
                <span className="how-step__number">Step {step.number}</span>
              </div>
              <h3 className="how-step__title">{step.title}</h3>
              <p className="how-step__body">{step.body}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
