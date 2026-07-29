import { useState } from "react";

export default function FinancialWellnessLanding() {
  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", background: "#fdfdf9", color: "#14171a", minHeight: "100vh", overflowX: "hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        @keyframes fadeUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulseGlow { 0%,100% { opacity: 0.55; transform: scale(1); } 50% { opacity: 0.9; transform: scale(1.08); } }
        @keyframes floatSlow { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
        @keyframes drift { 0%,100% { transform: translate(0,0); } 50% { transform: translate(-3%,2%); } }
        .fw-link { color: #4d7a12; text-decoration: none; }
        .fw-link:hover { color: #6ea617; }
        .fw-btn-primary { transition: background 0.15s; }
        .fw-btn-primary:hover { background: #94cc27 !important; }
        .fw-card { transition: transform 0.25s, box-shadow 0.25s; }
        .fw-card:hover { transform: translateY(-6px); box-shadow: 0 2px 4px rgba(20,23,26,0.06), 0 18px 36px rgba(20,23,26,0.14); }
      `}</style>

      {/* NAV */}
      <nav style={{ display: "flex", alignItems: "center", gap: 32, padding: "20px clamp(20px,5vw,64px)", position: "sticky", top: 0, zIndex: 20, background: "rgba(253,253,249,0.85)", backdropFilter: "blur(10px)", borderBottom: "1px solid rgba(20,23,26,0.08)" }}>
        <div style={{ fontWeight: 500, fontSize: 18, letterSpacing: "-0.01em", marginRight: "auto" }}>Financial&nbsp;Wellness</div>
        <a href="#how" className="fw-link" style={{ fontSize: 14, color: "#464b52" }}>How it works</a>
        <a href="#platform" className="fw-link" style={{ fontSize: 14, color: "#464b52" }}>Platform</a>
        <a href="/login" className="fw-link" style={{ fontSize: 14, color: "#464b52" }}>Log in</a>
        <a href="/signup" className="fw-btn-primary" style={{ display: "inline-flex", alignItems: "center", fontWeight: 500, fontSize: 14, color: "#3f6410", border: "1px solid #a6e22e", background: "#a6e22e", borderRadius: 8, padding: "8px 16px", textDecoration: "none" }}>Sign up</a>
      </nav>

      {/* HERO */}
      <section style={{ position: "relative", padding: "clamp(40px,8vw,96px) clamp(20px,5vw,64px) clamp(60px,8vw,110px)", display: "flex", gap: 48, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 480px", minWidth: 320, animation: "fadeUp 0.8s cubic-bezier(.2,.8,.2,1) both" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "#3f6410", background: "#eef8d9", border: "1px solid #cdea9a", borderRadius: 6, padding: "5px 10px", marginBottom: 22 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#6fae1a", animation: "pulseGlow 2.2s ease-in-out infinite" }} />
            Wearable-linked spending insight
          </span>
          <h1 style={{ fontWeight: 500, fontSize: "clamp(38px,4.6vw,58px)", lineHeight: 1.08, letterSpacing: "-0.02em", margin: "0 0 22px", maxWidth: "15ch" }}>
            Feel what your spending does to you — before it happens.
          </h1>
          <p style={{ fontSize: 17, lineHeight: 1.6, color: "#464b52", maxWidth: "46ch", margin: "0 0 32px" }}>
            Financial Wellness reads signals from your wearable, lines them up against your spending, and helps you catch the moment before an impulse becomes a transaction.
          </p>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 36 }}>
            <a href="/signup" className="fw-btn-primary" style={{ fontWeight: 500, fontSize: 15, color: "#3f6410", border: "1px solid #a6e22e", background: "#a6e22e", borderRadius: 8, padding: "12px 22px", textDecoration: "none" }}>Sign up free</a>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, letterSpacing: "0.02em", padding: "4px 11px", borderRadius: 6, background: "#f1f2ec", color: "#464b52" }}>Works with your bank</span>
            <span style={{ fontSize: 11, letterSpacing: "0.02em", padding: "4px 11px", borderRadius: 6, border: "1px solid #a6e22e", color: "#3f6410", background: "transparent" }}>Private by design</span>
            <span style={{ fontSize: 11, letterSpacing: "0.02em", padding: "4px 11px", borderRadius: 6, background: "#f1f2ec", color: "#464b52" }}>Optional manual entry</span>
          </div>
        </div>

        <div style={{ flex: "1 1 380px", minWidth: 300, position: "relative", display: "flex", justifyContent: "center", alignItems: "center", minHeight: 420 }}>
          <div style={{ position: "absolute", width: 340, height: 340, borderRadius: "50%", background: "radial-gradient(circle, rgba(166,226,46,0.35), transparent 70%)", filter: "blur(10px)", animation: "pulseGlow 4.5s ease-in-out infinite" }} />
          <div style={{ position: "relative", width: 300, height: 420, animation: "floatSlow 5.5s ease-in-out infinite", borderRadius: 28, background: "#eef1e6", display: "flex", alignItems: "center", justifyContent: "center", color: "#8a8f79", fontSize: 13, textAlign: "center", padding: 16 }}>
            {/* Replace with your product / wearable photo */}
            Product / wearable image
          </div>
        </div>
      </section>

      <div style={{ height: 1, margin: "0 clamp(20px,5vw,64px)", background: "linear-gradient(to right, transparent, rgba(20,23,26,0.12) 48px, rgba(20,23,26,0.12) calc(100% - 48px), transparent)" }} />

      {/* HOW IT WORKS */}
      <section id="how" style={{ padding: "clamp(60px,8vw,96px) clamp(20px,5vw,64px)" }}>
        <div style={{ maxWidth: 640, marginBottom: 48, animation: "fadeUp 0.7s cubic-bezier(.2,.8,.2,1) both" }}>
          <div style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: "#4d7a12", marginBottom: 10 }}>How it works</div>
          <h2 style={{ fontWeight: 500, fontSize: "clamp(26px,3vw,34px)", letterSpacing: "-0.015em", margin: 0 }}>Three signals, lined up in real time.</h2>
        </div>
        <div style={{ display: "flex", alignItems: "stretch", gap: 16, flexWrap: "wrap" }}>
          {[
            {
              step: "STEP 01", title: "Wear",
              body: "Your device reads arousal-linked indicators throughout the day — no extra input needed.",
              icon: (
                <svg width="22" height="22" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="7" stroke="#4d7a12" strokeWidth="1.6" /><path d="M13 4.5V2.5M13 23.5V21.5M4.5 13H2.5M23.5 13H21.5" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /></svg>
              ),
            },
            {
              step: "STEP 02", title: "Correlate",
              body: "We line those readings up against your transactions — bank-linked or entered by hand.",
              icon: (
                <svg width="22" height="22" viewBox="0 0 26 26" fill="none"><circle cx="9" cy="13" r="4.5" stroke="#4d7a12" strokeWidth="1.6" /><circle cx="17" cy="13" r="4.5" stroke="#4d7a12" strokeWidth="1.6" /></svg>
              ),
            },
            {
              step: "STEP 03", title: "Decide",
              body: "A virtual assistant explains the pattern in plain language, right when a decision is forming.",
              icon: (
                <svg width="22" height="22" viewBox="0 0 26 26" fill="none"><path d="M4 8a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H10l-4.5 4v-4H7a3 3 0 0 1-3-3V8Z" stroke="#4d7a12" strokeWidth="1.6" strokeLinejoin="round" /></svg>
              ),
            },
          ].map((s, i) => (
            <>
              <div key={s.title} className="fw-card" style={{ flex: "1 1 240px", minWidth: 220, display: "flex", flexDirection: "column", gap: 16, padding: "28px 24px", borderRadius: 14, background: "#ffffff", boxShadow: "0 1px 2px rgba(20,23,26,0.04), 0 10px 28px rgba(20,23,26,0.09)", animation: `fadeUp 0.6s cubic-bezier(.2,.8,.2,1) both`, animationDelay: `${0.05 + i * 0.1}s` }}>
                <div style={{ width: 44, height: 44, borderRadius: 12, background: "#eef8d9", display: "flex", alignItems: "center", justifyContent: "center" }}>{s.icon}</div>
                <div>
                  <div style={{ fontSize: 12, color: "#8a8f79", fontWeight: 500, letterSpacing: "0.06em", marginBottom: 6 }}>{s.step}</div>
                  <h3 style={{ fontWeight: 500, fontSize: 19, margin: "0 0 8px" }}>{s.title}</h3>
                  <p style={{ fontSize: 14, color: "#464b52", margin: 0, lineHeight: 1.6 }}>{s.body}</p>
                </div>
              </div>
              {i < 2 && (
                <div style={{ flex: "0 0 auto", display: "flex", alignItems: "center", justifyContent: "center", minWidth: 28, color: "#a6e22e" }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 12H20M20 12L14 6M20 12L14 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </div>
              )}
            </>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="platform" style={{ padding: "clamp(40px,6vw,64px) clamp(20px,5vw,64px) clamp(70px,8vw,100px)" }}>
        <div style={{ maxWidth: 640, marginBottom: 40 }}>
          <div style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: "#4d7a12", marginBottom: 10 }}>Platform</div>
          <h2 style={{ fontWeight: 500, fontSize: "clamp(26px,3vw,34px)", letterSpacing: "-0.015em", margin: "0 0 12px" }}>Everything for calmer money decisions.</h2>
          <p style={{ fontSize: 15, color: "#464b52", margin: 0, maxWidth: "52ch" }}>Four pieces, one loop: see your state, connect your spending, ask what it means, and set where you want to go.</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 20 }}>
          {[
            { title: "Dashboard", body: "A single view of your state trends alongside your spending, updated as your day moves.", icon: <svg width="26" height="26" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="10" stroke="#4d7a12" strokeWidth="1.6" /><path d="M13 13 L13 6.5" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /><path d="M13 13 L18 16" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /></svg> },
            { title: "Banking connect", body: "Link your bank or add transactions manually — every source lands in one feed.", icon: <svg width="26" height="26" viewBox="0 0 26 26" fill="none"><rect x="4" y="10" width="18" height="11" rx="2" stroke="#4d7a12" strokeWidth="1.6" /><path d="M4 10 L13 4 L22 10" stroke="#4d7a12" strokeWidth="1.6" strokeLinejoin="round" /><line x1="8" y1="14" x2="8" y2="17" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /><line x1="13" y1="14" x2="13" y2="17" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /><line x1="18" y1="14" x2="18" y2="17" stroke="#4d7a12" strokeWidth="1.6" strokeLinecap="round" /></svg> },
            { title: "AI insights", body: "A virtual assistant explains the correlation between your state and your spending, in plain language.", icon: <svg width="26" height="26" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="3.5" stroke="#4d7a12" strokeWidth="1.6" /><circle cx="13" cy="13" r="10" stroke="#4d7a12" strokeWidth="1.2" strokeDasharray="2 3" /></svg> },
            { title: "Goals & tracking", body: "Set a spending goal and watch how your state moves you toward or away from it.", icon: <svg width="26" height="26" viewBox="0 0 26 26" fill="none"><circle cx="13" cy="13" r="10" stroke="#4d7a12" strokeWidth="1.6" /><circle cx="13" cy="13" r="6" stroke="#4d7a12" strokeWidth="1.4" /><circle cx="13" cy="13" r="2" fill="#4d7a12" /></svg> },
          ].map((f, i) => (
            <div key={f.title} className="fw-card" style={{ display: "flex", flexDirection: "column", gap: 14, padding: 24, borderRadius: 12, background: "#ffffff", boxShadow: "0 1px 2px rgba(20,23,26,0.04), 0 10px 28px rgba(20,23,26,0.09)", animation: "fadeUp 0.6s cubic-bezier(.2,.8,.2,1) both", animationDelay: `${0.05 + i * 0.07}s` }}>
              {f.icon}
              <div style={{ fontWeight: 500, fontSize: 17 }}>{f.title}</div>
              <p style={{ fontSize: 13, color: "#5b6169", margin: 0, lineHeight: 1.55, flex: 1 }}>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* MISSION BAND */}
      <section style={{ position: "relative", padding: "clamp(70px,9vw,110px) clamp(20px,5vw,64px)", background: "#1e2a0d", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: "-10%", background: "radial-gradient(ellipse at 20% 30%, #33470f 0%, transparent 55%)", pointerEvents: "none", animation: "drift 9s ease-in-out infinite" }} />
        <div style={{ position: "relative", maxWidth: 720 }}>
          <div style={{ width: 32, height: 1, background: "#a6e22e", marginBottom: 24 }} />
          <p style={{ fontWeight: 400, fontSize: "clamp(22px,2.6vw,30px)", lineHeight: 1.4, letterSpacing: "-0.01em", margin: 0, color: "#f3f6ea" }}>
            Money decisions are emotional decisions. We built Financial Wellness to make that link visible — so you can act on it, not just feel it.
          </p>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ padding: "32px clamp(20px,5vw,64px) 40px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16, borderTop: "1px solid rgba(20,23,26,0.08)" }}>
        <div style={{ fontWeight: 500, fontSize: 15 }}>Financial&nbsp;Wellness</div>
        <div style={{ fontSize: 12, color: "#8a8f79" }}>A student internship project &middot; 2026</div>
      </footer>
    </div>
  );
}
