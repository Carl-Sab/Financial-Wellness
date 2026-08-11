import Button from "../Button";
import Reveal from "../Reveal";
import "./JoinBand.css";

export default function JoinBand() {
  return (
    <section className="join">
      <Reveal className="join__inner">
        <h2 className="join__heading">Want to join us?</h2>
        <p className="join__body">It takes a minute to get started.</p>
        <Button as="link" to="/signup" variant="dark" className="join__button">
          Sign up
        </Button>
      </Reveal>
    </section>
  );
}
