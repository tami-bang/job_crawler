import JobExplorer from "@/components/JobExplorer";
import SnapshotUpdatedAt from "@/components/SnapshotUpdatedAt";
import StatsPanel from "@/components/StatsPanel";

export default function Home() {
  return (
    <>
      <section className="hero dashboardHero">
        <div className="heroCopy">
          <div className="eyebrow"><span>01</span> DECISION DASHBOARD</div>
          <h1 className="text-4xl md:text-5xl lg:text-[52px] font-bold tracking-tight text-white whitespace-nowrap mt-4">
            나에게 딱 맞는 <span className="text-[#22c55e]">채용 공고 레이더</span>
          </h1>
        </div>
        <div className="heroSignal" aria-hidden="true"><i /><i /><i /><b>RADAR<br />ACTIVE</b></div>
      </section>
      <section className="contentSection dashboardOverview">
        <div className="sectionHeading">
          <div><span>OVERVIEW</span><h2>오늘의 지원 레이더</h2></div>
          <div className="sectionUpdate"><SnapshotUpdatedAt /><p>LOCAL DB · EXPLAINABLE SCORE</p></div>
        </div>
        <StatsPanel />
      </section>
      <section className="contentSection dashboardMatches">
        <div className="sectionHeading"><div><span>TOP MATCHES</span><h2>우선 확인할 공고</h2></div></div>
        <JobExplorer />
      </section>
    </>
  );
}
