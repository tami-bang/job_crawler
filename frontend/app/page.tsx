import JobExplorer from "@/components/JobExplorer";
import StatsPanel from "@/components/StatsPanel";

export default function Home() {
  return (
    <>
      <section className="hero dashboardHero">
        <div className="eyebrow"><span>01</span> DECISION DASHBOARD</div>
        <h1>흩어진 공고를<br /><em>지원할 이유</em>로.</h1>
        <p>자동 수집을 좇기보다, 내가 선택한 데이터에 집중합니다.<br />매칭 근거부터 지원 상태까지 한 화면에서 선명하게.</p>
        <div className="heroSignal" aria-hidden="true"><i /><i /><i /><b>RADAR<br />ACTIVE</b></div>
      </section>
      <section className="contentSection">
        <div className="sectionHeading"><div><span>OVERVIEW</span><h2>오늘의 지원 레이더</h2></div><p>LOCAL DB · EXPLAINABLE SCORE</p></div>
        <StatsPanel />
      </section>
      <section className="contentSection">
        <div className="sectionHeading"><div><span>TOP MATCHES</span><h2>우선 확인할 공고</h2></div></div>
        <JobExplorer />
      </section>
    </>
  );
}
