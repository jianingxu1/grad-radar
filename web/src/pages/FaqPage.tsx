import type { ReactNode } from "react";
import { PageHeader } from "../components/PageHeader";

export function FaqPage({ onNavigate }: { onNavigate: (path: "/") => void }) {
  return (
    <main className="flex min-h-screen flex-col bg-white text-slate-950">
      <div className="mx-auto w-full max-w-4xl flex-1 px-5 py-5 sm:px-8">
        <PageHeader label="Frequently asked questions" onNavigate={onNavigate} />

        <section aria-labelledby="faq-heading">
          <h2 className="text-3xl font-semibold tracking-tight" id="faq-heading">
            How GradRadar works
          </h2>
          <dl className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
            <FaqItem question="What jobs does GradRadar show?">
              Full-time U.S. entry-level software engineering roles from the new-grad sections of
              Simplify and SpeedyApply. It is designed for 2026 and 2027 bachelor&apos;s and
              master&apos;s graduates; PhD-specific roles are excluded.
            </FaqItem>
            <FaqItem question="How often is the feed updated?">
              GradRadar checks both trackers every 15 minutes from 7:00 AM through 8:45 PM Pacific.
              Overnight, it checks every two hours at 9:00 PM, 11:00 PM, 1:00 AM, 3:00 AM, and 5:00
              AM Pacific. A tracker is parsed only when its source file has changed.
            </FaqItem>
            <FaqItem question="What does “U.S.” mean here?">
              The filter keeps locations that clearly point to the United States, including U.S.
              states, common U.S. tech hubs, “United States,” and U.S.-eligible remote roles.
              Clearly non-U.S., mixed, or unknown locations are left out rather than guessed. This
              is a location filter, not a visa or sponsorship assessment.
            </FaqItem>
            <FaqItem question="Where do the listings come from?">
              The feed currently uses the Software Engineering new-grad section of Simplify and the
              USA new-grad SWE file from SpeedyApply. Each job shows its tracker source, so you can
              check the original listing context.
            </FaqItem>
            <FaqItem question="Are application links verified by GradRadar?">
              No. Application links are supplied by the source tracker. Open them to confirm the
              employer, requirements, deadline, location, and whether the position is still open.
            </FaqItem>
            <FaqItem question="What do “Listed” and tracker freshness mean?">
              “Listed” is the tracker&apos;s estimated posting age, not an employer-confirmed
              publish time. Tracker freshness shows when GradRadar last checked each source.
            </FaqItem>
            <FaqItem question="Does GradRadar require an account or track my applications?">
              No. The current feed is public and read-only. It does not submit applications or track
              application status.
            </FaqItem>
            <FaqItem question="How do I set up Telegram notifications to get the latest postings?">
              Log in first, then open the Notifications tab and click Connect. GradRadar will open
              Telegram with a start message for the GradRadar alert bot. Send that message to finish
              setup. To stop notifications, click Stop notifications in GradRadar or send /stop to
              the bot.
            </FaqItem>
          </dl>
        </section>
      </div>
      <footer className="border-t border-slate-200 px-5 py-5 sm:px-8">
        <div className="mx-auto max-w-4xl text-sm font-medium tracking-tight text-slate-400">
          © GradRadar
        </div>
      </footer>
    </main>
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
