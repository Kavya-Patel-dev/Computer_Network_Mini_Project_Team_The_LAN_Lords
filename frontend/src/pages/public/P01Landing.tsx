import React, { useState } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { useAuth } from '../../context/AuthContext';
import { 
  Network, 
  ShieldCheck, 
  Cpu, 
  BarChart, 
  CheckCircle2, 
  HelpCircle, 
  ChevronDown, 
  ChevronUp, 
  ArrowRight, 
  Activity, 
  Sliders, 
  Layers, 
  FileText 
} from 'lucide-react';

export const P01Landing: React.FC = () => {
  const { navigate } = useViewport();
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const faqs = [
    {
      q: 'Does NetRoute AI always beat Dijkstra routing?',
      a: 'No. As detailed in our benchmark data, under constrained tree topologies or sudden unannounced router hardware failures, load-aware Dijkstra or heuristic fallback performs equally well or slightly better. We believe in honest performance comparisons.',
    },
    {
      q: 'Can I connect physical switches or Cisco/Juniper hardware?',
      a: 'No. NetRoute AI is purely a discrete-event simulation studio designed for architectural evaluation, load balancing research, and topology planning.',
    },
    {
      q: 'Why do plans require administrator review?',
      a: 'To guarantee meaningful simulation runs, an administrator verifies that the graph is connected, consists of 5–50 routers, all host devices are leaf endpoints, and link bandwidth allocations are physically plausible.',
    },
    {
      q: 'What routing algorithms are evaluated?',
      a: 'Every simulation compares three strategies: (1) Static Dijkstra (fixed shortest path), (2) Load-aware Dijkstra (dynamic link delay penalty), and (3) AI Agent (imitation-trained behavior cloned policy with safe heuristic fallback).',
    },
    {
      q: 'What scenarios are tested?',
      a: 'Five distinct stress conditions: Normal operation, Link cut failure, Core router failure, 4x Traffic spike, and 50% Bandwidth degradation.',
    },
    {
      q: 'Can I share my simulation reports with clients or professors?',
      a: 'Yes! Every completed run can generate a secure, tokenized read-only link or be exported directly as a PDF or CSV package.',
    },
  ];

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text-primary">
      {/* Public Navigation */}
      <nav className="border-b border-brand-border bg-brand-surface/80 backdrop-blur-md sticky top-0 z-30 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-primary text-white flex items-center justify-center font-bold text-h3">
              NR
            </div>
            <span className="font-bold text-h2 text-brand-text-primary tracking-tight">NetRoute AI</span>
          </div>

          <div className="hidden md:flex items-center gap-6 text-body font-medium text-brand-text-secondary">
            <a href="#how-it-works" className="hover:text-brand-primary transition-colors">How it works</a>
            <a href="#features" className="hover:text-brand-primary transition-colors">Features</a>
            <a href="#honesty" className="hover:text-brand-primary transition-colors">Honest Modeling</a>
            <a href="#faq" className="hover:text-brand-primary transition-colors">FAQ</a>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/demo')}
              className="px-3.5 py-1.5 rounded-lg border border-brand-border text-brand-text-primary text-btn font-medium hover:bg-brand-bg"
            >
              Live Demo
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-1.5 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 shadow-sm"
            >
              Log In
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="px-6 pt-16 pb-20 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-brand-primary dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-800 text-caption font-semibold mb-6">
          <Activity className="w-4 h-4" />
          <span>Intelligent Network Routing Simulation Studio</span>
        </div>

        <h1 className="text-display font-extrabold text-brand-text-primary tracking-tight max-w-3xl mx-auto mb-6">
          See how AI routing handles congestion on your network
        </h1>

        <p className="text-body-l text-brand-text-secondary max-w-2xl mx-auto mb-10 leading-relaxed">
          Design custom network topologies, run multi-scenario stress simulations, and compare Static Dijkstra,
          Load-aware Dijkstra, and AI policies with rigorous, unvarnished benchmarks.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-14">
          <button
            onClick={() => navigate('/demo')}
            className="w-full sm:w-auto px-6 py-3 rounded-lg bg-brand-primary text-white text-btn font-semibold hover:opacity-90 flex items-center justify-center gap-2 shadow-md touch-target"
          >
            <span>Try the Demo</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => navigate('/register')}
            className="w-full sm:w-auto px-6 py-3 rounded-lg border border-brand-border bg-brand-surface text-brand-text-primary text-btn font-semibold hover:bg-brand-bg touch-target"
          >
            Create an Account
          </button>
        </div>

        {/* Live benchmark is shown only when a saved backend result exists. */}
        <div className="bg-brand-surface border border-brand-border rounded-xl p-6 shadow-xl text-left max-w-3xl mx-auto">
          <div className="flex items-center justify-between pb-3 border-b border-brand-border mb-4">
            <div>
              <span className="text-overline text-brand-text-muted">Model-backed evaluation</span>
              <h3 className="text-h3 font-bold text-brand-text-primary">Compare real saved simulation runs</h3>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-text-secondary">
              Live backend
            </span>
          </div>
          <p className="text-body text-brand-text-secondary">There is no public benchmark fixture configured. Sign in, create a topology, submit it for review, then open its saved run to compare the frozen AI model with routing baselines.</p>
          <button onClick={() => navigate('/register')} className="mt-4 px-4 py-2 rounded-lg bg-brand-primary text-white text-btn font-semibold">Create account</button>
        </div>
      </section>

      {/* How It Works (4 Steps) */}
      <section id="how-it-works" className="py-16 bg-brand-surface border-y border-brand-border px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-overline text-brand-primary">Workflow</span>
            <h2 className="text-h1 font-bold text-brand-text-primary mt-1">How NetRoute AI Operates</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-5 bg-brand-bg border border-brand-border rounded-lg relative">
              <span className="text-kpi font-extrabold text-brand-primary/20 absolute top-2 right-4">01</span>
              <Layers className="w-6 h-6 text-brand-primary mb-3" />
              <h3 className="text-h3 font-semibold text-brand-text-primary mb-1">Describe Network</h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                Draw on our interactive canvas, fill tabular forms, upload JSON/GraphML, or generate from floor requirements.
              </p>
            </div>

            <div className="p-5 bg-brand-bg border border-brand-border rounded-lg relative">
              <span className="text-kpi font-extrabold text-brand-primary/20 absolute top-2 right-4">02</span>
              <ShieldCheck className="w-6 h-6 text-amber-500 mb-3" />
              <h3 className="text-h3 font-semibold text-brand-text-primary mb-1">Admin Review</h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                An administrator verifies graph connectivity, router bounds (5–50), and reasonable bandwidth provisioning.
              </p>
            </div>

            <div className="p-5 bg-brand-bg border border-brand-border rounded-lg relative">
              <span className="text-kpi font-extrabold text-brand-primary/20 absolute top-2 right-4">03</span>
              <Cpu className="w-6 h-6 text-emerald-500 mb-3" />
              <h3 className="text-h3 font-semibold text-brand-text-primary mb-1">Simulate Scenarios</h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                Run 3 routing strategies across 5 scenarios: Normal, Link cut, Router failure, Traffic spikes, and Bandwidth drop.
              </p>
            </div>

            <div className="p-5 bg-brand-bg border border-brand-border rounded-lg relative">
              <span className="text-kpi font-extrabold text-brand-primary/20 absolute top-2 right-4">04</span>
              <BarChart className="w-6 h-6 text-purple-500 mb-3" />
              <h3 className="text-h3 font-semibold text-brand-text-primary mb-1">Compare & Explain</h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                Examine plain-language verdicts, time-series telemetry, dynamic heatmaps, and router attention Q-values.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Honest Rule: What This Is and What This Is Not */}
      <section id="honesty" className="py-16 px-6 max-w-4xl mx-auto">
        <div className="border border-brand-border rounded-xl p-8 bg-brand-surface shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <HelpCircle className="w-6 h-6 text-brand-primary" />
            <h2 className="text-h2 font-bold text-brand-text-primary">What NetRoute AI Is — And What It Is Not</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-body">
            <div className="space-y-3">
              <h3 className="text-h3 font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5" /> What It Is
              </h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • A rigorous routing simulation laboratory for researchers and enterprise planners.
              </p>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • A fair, honest comparison tool evaluating Packet Loss, Latency, Throughput, and Flapping.
              </p>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • An explainable platform displaying candidate path Q-values and heuristic fallback alerts.
              </p>
            </div>

            <div className="space-y-3">
              <h3 className="text-h3 font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 rotate-45" /> What It Is Not
              </h3>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • It is <strong>NOT</strong> magic: the AI does not always win and never claims 100% "accuracy".
              </p>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • It does <strong>NOT</strong> configure physical hardware, switch firmware, or real VLAN tags.
              </p>
              <p className="text-caption text-brand-text-secondary leading-relaxed">
                • It is <strong>NOT</strong> an unmonitored production controller.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Accordion */}
      <section id="faq" className="py-16 bg-brand-surface border-t border-brand-border px-6">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-10">
            <span className="text-overline text-brand-primary">FAQ</span>
            <h2 className="text-h1 font-bold text-brand-text-primary mt-1">Frequently Asked Questions</h2>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, idx) => (
              <div
                key={idx}
                className="bg-brand-bg border border-brand-border rounded-lg overflow-hidden transition-all"
              >
                <button
                  onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                  className="w-full text-left p-4 flex items-center justify-between text-body font-semibold text-brand-text-primary hover:text-brand-primary"
                >
                  <span>{faq.q}</span>
                  {openFaq === idx ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {openFaq === idx && (
                  <div className="px-4 pb-4 text-caption text-brand-text-secondary leading-relaxed border-t border-brand-border/60 pt-3">
                    {faq.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-brand-border py-8 px-6 text-center text-caption text-brand-text-muted">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© 2026 The LAN Lords • NetRoute AI Simulation Studio</p>
          <div className="flex gap-4">
            <button onClick={() => navigate('/demo')} className="hover:underline">Demo</button>
            <button onClick={() => navigate('/login')} className="hover:underline">Login</button>
            <button onClick={() => navigate('/403')} className="hover:underline">Access Policy</button>
          </div>
        </div>
      </footer>
    </div>
  );
};
