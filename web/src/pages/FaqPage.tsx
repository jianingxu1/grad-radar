import type { ReactNode } from "react";
import { PageShell } from "../components/PageShell";

export function FaqPage({ onNavigate }: { onNavigate: (path: "/") => void }) {
  return (
    <PageShell label="Frequently asked questions" onNavigate={onNavigate}>

        <section aria-labelledby="faq-heading">
          <h2 className="text-3xl font-semibold tracking-tight" id="faq-heading">
            How GradRadar works
          </h2>
          <dl className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
            <FaqItem question="What jobs does GradRadar show?">
              Full-time U.S. entry-level software engineering roles for 2026 and 2027
              bachelor&apos;s and master&apos;s graduates. GradRadar checks the new-grad sections of
              Simplify and SpeedyApply, along with specific company job boards listed on the
              Sources page. PhD-specific roles are excluded.
            </FaqItem>
            <FaqItem question="How often is the feed updated?">
              The feed is updated every 15 minutes.
            </FaqItem>
            <FaqItem question="Where do the listings come from?">
              GradRadar collects listings from community trackers and selected company career
              boards. The Sources page shows which trackers and company boards are currently
              checked. Listings include links to their source, so you can review the original
              posting and application details.
            </FaqItem>
            <FaqItem question="Are application links verified by GradRadar?">
              No. Application links are supplied by the source tracker. Open them to confirm the
              employer, requirements, deadline, location, and whether the position is still open.
            </FaqItem>
            <FaqItem question="What do “Listed” and tracker freshness mean?">
              “Listed” is the tracker&apos;s estimated posting age, not an employer-confirmed
              publish time. Tracker freshness shows when GradRadar last checked each source.
            </FaqItem>
            <FaqItem question="How do I set up Telegram notifications to get the latest postings?">
              Log in first, then open the Notifications tab. Follow the instructions there.
            </FaqItem>
          </dl>
        </section>
    </PageShell>
  );
}

function FaqItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <div className="py-6">
      <dt className="text-base font-semibold">{question}</dt>
      <dd className="mt-2 max-w-3xl leading-7 text-slate-600">{children}</dd>
    </div>
  );
}
