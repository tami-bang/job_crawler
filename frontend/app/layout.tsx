import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job Radar — 지원 결정을 선명하게",
  description: "수집된 채용공고를 개인 기준으로 탐색하고 관리하는 대시보드",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const dataMode = process.env.NEXT_PUBLIC_STATIC_DEMO === "true" ? "DEMO DATA" : "LOCAL DATA";
  return (
    <html lang="ko">
      <body>
        <div className="ambient ambientOne" />
        <div className="ambient ambientTwo" />
        <header className="siteHeader">
          <Link className="brand" href="/">
            JOB<span>RADAR</span><i>●</i>
          </Link>
          <nav aria-label="주요 메뉴">
            <Link href="/">대시보드</Link>
            <Link href="/jobs">공고 탐색</Link>
            <Link href="/favorites">관심공고</Link>
            <Link href="/updates">업데이트 로그</Link>
          </nav>
          <div className="systemState"><i /> {dataMode}</div>
        </header>
        <main>{children}</main>
        <footer>JOB RADAR · 데이터는 로컬에서, 결정은 나답게.</footer>
      </body>
    </html>
  );
}
