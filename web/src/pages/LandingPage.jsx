import Header from "../components/landing/Header";
import Hero from "../components/landing/Hero";
import Features from "../components/landing/Features";
import HowItWorks from "../components/landing/HowItWorks";
import JoinBand from "../components/landing/JoinBand";
import Footer from "../components/landing/Footer";

export default function LandingPage() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Header />
      <main id="main-content" tabIndex={-1}>
        <Hero />
        <Features />
        <HowItWorks />
        <JoinBand />
      </main>
      <Footer />
    </>
  );
}
